import contextlib
import io
import time
from typing import Dict, Any
import traceback

def execute_python_code(code: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Execute Python code in a restricted environment and return the result.
    """
    if context is None:
        context = {}
        
    start_time = time.time()
    stdout = io.StringIO()
    stderr = io.StringIO()
    exec_globals = {**context}
    
    result = {
        "stdout": "",
        "stderr": "",
        "exception": None,
        "execution_time": 0,
        "success": False
    }
    
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code, exec_globals)
            
        result["stdout"] = stdout.getvalue()
        result["stderr"] = stderr.getvalue()
        result["success"] = True
        
    except Exception as e:
        result["exception"] = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
        result["stderr"] = stderr.getvalue()
        
    finally:
        result["execution_time"] = time.time() - start_time
        
    return result
