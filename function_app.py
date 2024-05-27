import azure.functions as func
import json
import logging
from time import time
from azure.storage.blob import BlobServiceClient
import base64
import os
import requests

# Initialize the Function App with HTTP authentication level set to FUNCTION
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Configuration variables retrieved from environment variables
connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
container_name = os.getenv('CONTAINER_NAME')
refresh_url = os.getenv('REFRESH_URL')
chatbot_url = os.getenv('CHATBOT_URL')
api_key = os.getenv('API_KEY')

# Initialize the BlobServiceClient with the connection string
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

def make_post_request(url, api_key, json_data=None):
    """
    Makes a POST request to the specified URL with the provided API key and JSON data.
    This is like a bridge between the Frontend and the Backend services.

    Args:
        url (str): The URL to send the POST request to.
        api_key (str): The API key to include in the request headers for authentication.
        json_data (dict, optional): The JSON data to include in the request body. Defaults to None.

    Returns:
        func.HttpResponse: The response from the server.

    Raises:
        None
    """
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    response = requests.post(url, headers=headers, json=json_data)
    response_body = response.json()
    
    # Return error response if "body" attribute is missing in the response
    if "body" not in response_body:
        return func.HttpResponse(
            body="An internal server error occurred",
            status_code=response.status_code
        )

    # Return the actual response body with the same status code and content type
    return func.HttpResponse(
        body=response_body["body"],
        status_code=response.status_code,
        headers={"Content-Type": "application/json"}
    )

def method_not_allowed():
    """
    Returns an HTTP response with status code 405 (Method Not Allowed).

    Args:
        None

    Returns:
        func.HttpResponse: The HTTP response object with status code 405.
    """
    return func.HttpResponse("Method not allowed", status_code=405)

@app.route(route="refresh", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def refresh(req: func.HttpRequest) -> func.HttpResponse:
    """
    Refreshes the index by making a POST request to the refresh URL.

    Args:
        req (func.HttpRequest): The HTTP request object.

    Returns:
        func.HttpResponse: The HTTP response object containing the result of the refresh operation.
    """
    # Track the start time to measure processing time
    start = time()
    logging.info(f"Processing a request to refresh the index. Start time: {start}")
    
    # Check if the request method is HTTP POST.
    if req.method != 'POST':
        return method_not_allowed()

    # Make a POST request to the refresh URL with the API key.
    logging.info(f"Making a POST request to the refresh URL: {refresh_url}")
    response = make_post_request(refresh_url, api_key)
    response_body = json.loads(response.get_body().decode('utf-8'))

    # Add processing time to the response
    processing_time = time() - start
    response['processing_time_seconds'] = processing_time
    logging.info(f"Processing time: {processing_time} seconds")
    
    return func.HttpResponse(
        body=json.dumps(response_body),
        status_code=response.status_code,
        headers={"Content-Type": "application/json"}
    )

# Route to handle chatbot requests by making a POST request to the specified URL with JSON data
@app.route(route="chatbot", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def chatbot(req: func.HttpRequest) -> func.HttpResponse:
    # Track the start time to measure processing time
    start = time()
    logging.info(f"Processing a request to the chatbot. Start time: {start}")
    
    # Check if the request method is HTTP POST.
    if req.method != 'POST':
        return method_not_allowed()

    # Make a POST request to the chatbot URL with the API key and JSON data.
    logging.info(f"Making a POST request to the chatbot URL: {chatbot_url}")
    response = make_post_request(chatbot_url, api_key, req.get_json())
    response_body = json.loads(response.get_body().decode('utf-8'))

    # Add processing time to the response
    processing_time = time() - start
    response['processing_time_seconds'] = processing_time
    logging.info(f"Processing time: {processing_time} seconds")
    
    return func.HttpResponse(
        body=json.dumps(response_body),
        status_code=response.status_code,
        headers={"Content-Type": "application/json"}
    )


@app.route(route="upload", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload(req: func.HttpRequest) -> func.HttpResponse:
    """
    Uploads a file to Azure Blob Storage.

    Args:
        req (func.HttpRequest): The HTTP request object.

    Returns:
        func.HttpResponse: The HTTP response object.
    """
    # Track the start time to measure processing time
    start = time()
    logging.info(f"Processing a request to upload a file. Start time: {start}")

    # Check if the request method is HTTP POST.
    if req.method != 'POST':
        return method_not_allowed()
    
    # Get the request body as a string
    # Return an error response if the request body is empty
    req_body = req.get_body().decode('utf-8') if req.get_body() else None
    if not req_body:
        return func.HttpResponse("Request body is empty", status_code=400)
    
    # Parse the JSON body, extract the file content (base64 encoded), and the filename
    data = json.loads(req_body)
    file = data.get('file')
    pdf_name = data.get('filename')

    # Return an error response if the file or filename is not provided in the request
    if not file or not pdf_name:
        return func.HttpResponse("File or filename not provided in the request", status_code=400)
    
    # Initialize the response dictionary with the 'loaded' key set to False
    response = {'loaded': False}

    try:
        # Decode the base64 file content
        decoded_bytes = base64.b64decode(file, validate=True)
        # Get the BlobClient for the specified container and PDF filename
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=pdf_name)
        # Upload the file to Azure Blob Storage
        blob_client.upload_blob(decoded_bytes, overwrite=True)
        # Set the 'loaded' key in the response dictionary to True
        response['loaded'] = True
    except Exception as e:
        logging.error(f"ERROR: {e}")

    # Calculate the processing time and add it to the response dictionary
    processing_time = time() - start
    response['processing_time_seconds'] = processing_time
    logging.info(f"Processing time: {processing_time} seconds")

    # Return the response as a JSON string with a status code of 200
    return func.HttpResponse(body=json.dumps(response), status_code=200)
