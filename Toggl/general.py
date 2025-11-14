import requests
import logging

def get_project_name(api_token: str, project_id: int, workspace_id: int) -> str:
    """
    Fetches the project name from the Toggl API. 
    Handles 404 (Not Found) errors gracefully.
    """
    if not project_id or not api_token or not workspace_id:
        return "Unknown Project"

    PROJECT_URL = f"https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/projects/{project_id}"
    
    try:
        response = requests.get(
            PROJECT_URL,
            auth=(api_token, 'api_token')
        )
        response.raise_for_status()
        
        if response.text and response.text != '{}':
            project_data = response.json()
            return project_data.get('name', 'Unknown Project (API failure)')
        else:
            return "Project not found"
            
    except requests.exceptions.HTTPError as errh:
        # Check for 404 specifically, which indicates the project is inaccessible or deleted.
        if errh.response.status_code == 404:
            logging.warning(f"Project ID {project_id} not found or inaccessible for the provided token.")
            return "Inaccessible or Deleted Project"
        
        # Handle other HTTP errors (401, 500, etc.)
        logging.error(f"HTTP Error fetching project {project_id}: {errh}")
        return f"HTTP Error: {errh.response.status_code}"

    except requests.exceptions.RequestException as err:
        logging.error(f"Network Error fetching project {project_id}: {err}")
        return f"Network Error: {err}"
    
def format_duration(seconds):
    """
    Converts a duration in seconds to a human-readable H:MM:SS format,
    where the hours component includes the total number of hours (including days).
    """
    total_seconds = int(seconds)
    
    # Calculate total hours, minutes, and remaining seconds
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60
    
    # Format the result as H:MM:SS
    # Use the format string to ensure minutes and seconds are always 2 digits
    return f"{hours}:{minutes:02}:{remaining_seconds:02}"

