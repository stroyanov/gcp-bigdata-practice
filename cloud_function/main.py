import requests
import os

METADATA_URL = 'http://metadata.google.internal/computeMetadata/v1/'
METADATA_HEADERS = {'Metadata-Flavor':'Google'}
SERVICE_ACCOUNT = 'default' #You may replace this with the Service Account you're using if you're using a SA other than the default

# Now we assemble the Data Fusion URL we will send the request to, according to the Data Fusion REST API docs: https://cloud.google.com/data-fusion/docs/reference/cdap-reference#start_a_batch_pipeline
CDAP_INSTANCE_ENDPOINT = "[YOUR_CDAP_INSTANCE_ENDPOINT]"
PIPELINE_NAME = "[YOUR_PIPELINE_NAME]"
CDAP_PIPELINE_URL = '{}/v3/namespaces/default/apps/{}/workflows/DataPipelineWorkflow/start'.format(CDAP_INSTANCE_ENDPOINT, PIPELINE_NAME)


def get_access_token():

    url = '{}instance/service-accounts/{}/token'.format(METADATA_URL, SERVICE_ACCOUNT)

    # Request an access token from the metadata server.
    r = requests.get(url, headers=METADATA_HEADERS)
    print("Getting authentication token")
    print(r.raise_for_status())

    # Extract the access token from the response.
    access_token = r.json()['access_token']

    return access_token

def main(event, context):
    """Triggered by a change to a Cloud Storage bucket.
    Args:
    event (dict): Event payload.
    context (google.cloud.functions.Context): Metadata for the event.
    """
    file = event
    print(f"Processing file: {file['name']}.")
    token = get_access_token()
    print(token)

    # Here we obtain the filename of the file that was uploaded to the Storage Bucket and triggered this Cloud Function.
    # We will pass it as part of the body of the request to the Data Fusion REST API so that Data Fusion can use it as a Runtime Argument in the pipeline
    REQ_BODY = {"FileName" : os.path.split(file['name'])[1]}
    print(REQ_BODY)

    # Finally we send the POST request to the to start the execution of the data pipeline with the URL we assembled, the body with the name of the File to be processed and the access token
    r = requests.post(CDAP_PIPELINE_URL, json=REQ_BODY, headers={"Authorization":"Bearer {}".format(token)})
    print(r.raise_for_status())