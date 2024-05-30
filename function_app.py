import azure.functions as func
import json
import logging
from time import time
from azure.storage.blob import BlobServiceClient
import base64
import os
import requests

# Initialize the Function App with HTTP authentication level set to Anonymous
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Configuration variables retrieved from environment variables
connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
container_name = os.environ.get('CONTAINER_NAME')
refresh_url = os.environ.get('REFRESH_URL')
chatbot_url = os.environ.get('CHATBOT_URL')
api_key = os.environ.get('API_KEY')

# Initialize the BlobServiceClient with the connection string
blob_service_client = BlobServiceClient.from_connection_string(
    connection_string)


def make_post_request(url, api_key, json_data={}):
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
    if response.status_code != 200:
        logging.error(
            f"An error occurred while making a POST request to {url} (HTTP {response.status_code}): {response.text}"
        )
        return func.HttpResponse(
            body=json.dumps({"result": "Internal Server Error"}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

    logging.info(
        f"Successfully made a POST request to {url} (HTTP {response.status_code}): {response.text}"
    )

    try:
        response_body = response.json()
        logging.info(f"Response body: {response_body}")
    except json.JSONDecodeError:
        logging.warning(
            f"The response from {url} is not a valid JSON string, returning the response as is: {response.text}"
        )
        return func.HttpResponse(
            body=json.dumps({"result": response.text}),
            status_code=response.status_code,
            headers={"Content-Type": "application/json"}
        )

    if "body" not in response_body:
        logging.error(
            f"No 'body' key found in the response from {url}, returning an internal server error response"
        )
        return func.HttpResponse(
            body=json.dumps({"result": "Internal Server Error"}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

    # Return the actual response body with the same status code and content type
    return func.HttpResponse(
        body=json.dumps(response_body["body"]),
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


@app.route(route="refresh", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
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
    logging.info(
        f"Processing a request to refresh the index. Start time: {start}")

    # Check if the request method is HTTP POST.
    if req.method != 'POST':
        return method_not_allowed()

    # Make a POST request to the refresh URL with the API key.
    logging.info(f"Making a POST request to the refresh URL: {refresh_url}")
    response = make_post_request(refresh_url, api_key)
    response_body = json.loads(response.get_body().decode('utf-8'))

    # Log the processing time and add it to the response
    processing_time = time() - start
    response_body['processing_time_seconds'] = processing_time
    logging.info(f"Processing time: {processing_time} seconds")

    return func.HttpResponse(
        body=json.dumps(response_body),
        status_code=response.status_code,
        headers={"Content-Type": "application/json"}
    )

# Route to handle chatbot requests by making a POST request to the specified URL with JSON data


@app.route(route="chatbot", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def chatbot(req: func.HttpRequest) -> func.HttpResponse:
    # Track the start time to measure processing time
    start = time()
    logging.info(f"Processing a request to the chatbot. Start time: {start}")

    # Check if the request method is HTTP POST.
    if req.method != 'POST':
        return method_not_allowed()

    # Get the request body as a string
    # Return an error response if the request body is empty
    req_body = req.get_body().decode('utf-8') if req.get_body() else None
    if not req_body:
        return func.HttpResponse("Request body is empty", status_code=400)

    # Parse the JSON body and obtain the question.
    data = json.loads(req_body)
    question = data.get('message')

    # Return an error response if the question is not provided in the request
    if not question:
        return func.HttpResponse("'message' not provided in the request", status_code=400)

    # Make a POST request to the chatbot URL with the API key and the question
    logging.info(f"Making a POST request to the chatbot URL: {chatbot_url}")
    response = make_post_request(chatbot_url, api_key, {"message": question})
    response_body = json.loads(response.get_body().decode('utf-8'))

    # Log the processing time and add it to the response
    processing_time = time() - start
    response_body['processing_time_seconds'] = processing_time
    logging.info(f"Processing time: {processing_time} seconds")

    return func.HttpResponse(
        body=json.dumps(response_body),
        status_code=response.status_code,
        headers={"Content-Type": "application/json"}
    )


@app.route(route="upload", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
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

    # Parse the JSON body and obtain the file name and file content
    data = json.loads(req_body)
    file_name = data.get('filename')
    file_content = data.get('file')

    # Return an error response if the file name or file content is not provided in the request
    if not file_name or not file_content:
        return func.HttpResponse(
            body=json.dumps(
                {"result": "File name or file content not provided in the request"}),
            status_code=400,
            headers={"Content-Type": "application/json"}
        )

    # Decode the base64-encoded file content
    response = {
        "loaded": False,
        "processing_time_seconds": 0
    }

    try:
        file_content = base64.b64decode(file_content)

        # Get the BlobClient for the specified file name
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=file_name
        )

        # Upload the file content to the Blob Storage
        blob_client.upload_blob(file_content, overwrite=True)
        response["loaded"] = True
    except Exception as e:
        logging.error(f"An error occurred while uploading the file: {e}")
        return func.HttpResponse(
            body=json.dumps({"result": "Internal Server Error"}),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

    # Log the processing time and add it to the response
    processing_time = time() - start
    logging.info(f"Processing time: {processing_time} seconds")
    response["processing_time_seconds"] = processing_time

    return func.HttpResponse(
        body=json.dumps(response),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )
