from fastapi import FastAPI, HTTPException
import httpx
import re
from urllib.parse import urlparse
from codegen import Codebase
from codegen.shared.enums.programming_language import ProgrammingLanguage
from codegen.git.repo_operator.repo_operator import RepoOperator
from codegen.git.schemas.repo_config import RepoConfig
from codegen.sdk.codebase.config import ProjectConfig
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl

# Models for Request/Response
class RepoRequest(BaseModel):
    github_url: HttpUrl
    branch: Optional[str] = "main"

class PromiseConversion(BaseModel):
    file_path: str
    function_name: str
    promises_found: int
    promises_converted: int

class ConversionResponse(BaseModel):
    status: str
    repository: str
    statistics: Dict[str, int]
    converted_functions: List[PromiseConversion]
    error: Optional[str] = None

class VerificationResponse(BaseModel):
    repository: str
    is_javascript_typescript: bool
    languages: Dict[str, int]

def parse_github_url(url: str) -> tuple:
    """Extract owner and repo from GitHub URL."""
    match = re.search(r"github\.com/([^/]+)/([^/]+)", str(url))
    if not match:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    return match.group(1), match.group(2)

# Load environment variables
load_dotenv()

# Get GitHub token from environment
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    raise Exception("GITHUB_TOKEN environment variable is required")

app = FastAPI(title="GitHub Repository Analyzer")

@app.get("/")
async def root():
    return {"message": "GitHub Repository Analyzer API"}

@app.post("/verify", response_model=VerificationResponse)
async def verify_repository(request: RepoRequest):
    """
    Verify if a GitHub repository is TypeScript/JavaScript based.
    """
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # Parse URL to ensure it's from GitHub
    parsed_url = urlparse(str(request.github_url))
    if parsed_url.netloc != "github.com":
        raise HTTPException(status_code=400, detail="URL must be from github.com")
    
    # Extract owner and repo from URL
    path_parts = parsed_url.path.strip('/').split('/')
    if len(path_parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    
    owner, repo = path_parts[0], path_parts[1]
    repo_full_name = f"{owner}/{repo}"
    
    # Call GitHub API to get repository languages
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/languages",
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"GitHub API error: {response.text}"
                )
                
            languages = response.json()
            
            # Check if repo contains JavaScript or TypeScript
            is_js_ts = any(lang.lower() in ["javascript", "typescript"] for lang in languages.keys())
            
            return VerificationResponse(
                repository=repo_full_name,
                is_javascript_typescript=is_js_ts,
                languages=languages
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/process-js-ts")
async def process_js_ts_repository(github_url: str):
    """
    Process only TypeScript/JavaScript repositories.
    Returns an error if the repository is not TypeScript/JavaScript based.
    """
    # First verify if the repository is JS/TS based
    verification_result = await verify_repository(RepoRequest(github_url=github_url))
    
    if not verification_result.is_javascript_typescript:
        raise HTTPException(
            status_code=400,
            detail="Repository must be TypeScript/JavaScript based"
        )
    
    # Return the processed result
    return {
        "repository": verification_result.repository,
        "languages": {
            k: v for k, v in verification_result.languages.items()
            if k.lower() in ["javascript", "typescript"]
        }
    }

def get_function_line_number(function) -> int:
    """Helper function to safely get function line number."""
    try:
        source_lines = function.source.split('\n')
        return len(source_lines) if source_lines else 1
    except Exception:
        return 1

def create_error_response(github_url: str, repo_path: str = None, error_detail: str = None) -> ConversionResponse:
    """Helper function to create error responses with consistent format."""
    return ConversionResponse(
        status="error",
        repository=repo_path if repo_path else str(github_url).split("github.com/")[-1].rstrip("/"),
        statistics={
            "files_scanned": 0,
            "promise_chains_found": 0,
            "promises_converted": 0,
            "files_modified": 0
        },
        converted_functions=[],
        error=error_detail
    )

@app.post("/convert-to-async", response_model=ConversionResponse)
async def convert_to_async(request: RepoRequest):
    """
    Convert .then() promise chains to async/await syntax in a TypeScript/JavaScript repository.
    """
    try:
        # Extract owner/repo from GitHub URL
        match = re.search(r"github\.com/([^/]+/[^/]+)", str(request.github_url))
        if not match:
            raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
        
        repo_path = match.group(1)
        
        # Initialize codebase directly
        try:
            codebase = Codebase.from_repo(repo_path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize codebase: {str(e)}"
            )
        
        # Track conversions
        converted_functions = []
        conversion_stats = {
            "files_scanned": len(codebase.files),
            "promise_chains_found": 0,
            "promises_converted": 0,
            "files_modified": 0
        }
        
        # Process each function's promise chains
        for function in codebase.functions:
            if hasattr(function, 'promise_chains') and function.promise_chains:
                conversion_stats["promise_chains_found"] += len(function.promise_chains)
                
                try:
                    # Convert each promise chain
                    for chain in function.promise_chains:
                        chain.convert_to_async_await()
                        conversion_stats["promises_converted"] += 1
                    
                    # Track converted function
                    converted_functions.append(PromiseConversion(
                        file_path=function.filepath,
                        function_name=function.name,
                        promises_found=len(function.promise_chains),
                        promises_converted=len(function.promise_chains)
                    ))
                    
                    if function.filepath not in set(cf.file_path for cf in converted_functions):
                        conversion_stats["files_modified"] += 1
                except Exception as e:
                    continue
        
        # Commit changes if any functions were converted
        if converted_functions:
            try:
                codebase.commit()
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to commit changes: {str(e)}"
                )
        
        return ConversionResponse(
            status="success",
            repository=repo_path,
            statistics=conversion_stats,
            converted_functions=converted_functions
        )
        
    except HTTPException as he:
        return create_error_response(request.github_url, repo_path if 'repo_path' in locals() else None, he.detail)
    except Exception as e:
        return create_error_response(request.github_url, repo_path if 'repo_path' in locals() else None, str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)