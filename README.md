# GCP Big Data Practice Project

## Summary
Architecture description for bigdata project with GCP services.

It provides a detailed solution to do just that using Data storage, Processing and Analytics with Google Cloud Platform.

In this project a Cloud Data Fusion Pipeline execution will be triggered automatically with a Cloud Function every time a new data file is uploaded to a Google Cloud Storage Bucket, this data pipeline will then perform some transformations on the data and load the results into a BigQuery table which feeds a report with a couple of visualizations created in Data Studio.

## Architecture
![gcp-practice drawio](/images/basic-diagram.png)

### GCP Services used for solution
- Google Cloud Storage
- Google Cloud Functions
- Google Cloud Data Fusion
- Google BigQuery
- Google Data Studio

### Description of the solution
The idea is to create a very simple report in Data Studio that feeds from a table previously created and loaded in BigQuery. The source data resides in a single cumulative CSV file on premise that needs to be somewhat transformed before being loaded into BigQuery, so a data transformation pipeline in Data Fusion handles the transformations required on the file and ingests the results in the BigQuery table, by truncating the table first (although with the change of literally one flag in the Data Fusion pipeline you may modify it to append data in the BigQuery table rather than truncating the table every single run). The source file is updated continuously and is uploaded to Google Cloud Storage many times a day in an on-demand fashion, we don’t know when a new file may arrive but we know we need to refresh the report with any new data that arrives as soon as it does, so we use a Cloud Function to trigger the Data Fusion pipeline upon the event of a new CSV file being uploaded to the Cloud Storage bucket. In this way, the whole process of data ingestion, transformation, load and visualization is triggered by simply uploading a new data file to a Google Cloud Storage bucket.

### Main steps
1. Create the storage buckets we will use and prepare the source CSV file to be used to create the transformation pipeline.
2. Create the Dataset and table in BigQuery that will store the data from the CSV file.
3. Create the Data Fusion instance and assign proper roles to the Service Account it will use.
4. Within the Data Fusion instance, create the Data Pipeline that will process the new CSV files and ingest them into the BigQuery table.
5. Create the Cloud Function that will be triggered when a new file is uploaded to the defined Storage bucket, and will pass the newly added file to the Data Fusion pipeline for processing and ingestion to BigQuery.
6. Create a simple report in Data Studio with some visualizations of the data in BigQuery.

## Steps

<details>
<summary>Environment preparation</summary>

Install gsutil https://cloud.google.com/storage/docs/gsutil_install

How to use gsutil and useful commands is described here https://cloud.google.com/storage/docs/gsutil  

</details>

<details>
<summary>Create buckets that will be used for the data processing</summary>


Using the [cloud shell](https://cloud.google.com/shell/docs/launching-cloud-shell), create the following buckets in Cloud Storage. You can name them however you like, they just need to be unique, you will need to provide these later in future steps (remember to replace the bucket name in brackets [], with your own bucket names):

`gsutil mb gs://[YOUR_DATA_SOURCE_BUCKET]` where is YOUR_DATA_SOURCE_BUCKET = csv-load-raw-source  

Bucket for raw CSV source files to be uploaded to GCP (files uploaded to this bucket will trigger the data transformation and data load process, this bucket will be used when writing the Cloud Function as the triggering event of the function).

`gsutil mb gs://[YOUR_CDAP_TEMP_BUCKET]` where is YOUR_CDAP_TEMP_BUCKET = test-cdap-staging

Staging bucket that the Data Fusion pipeline will use as temporary store while inserting data into BigQuery.

`gsutil mb gs://[YOUR_CDAP_ERRORS_BUCKET]` where is YOUR_CDAP_ERRORS_BUCKET = test-cdap-errors

Bucket that will hold the output of any errors during the data processing in the Cloud Data Fusion pipeline.

Finally, we will upload a sample CSV file with a subset of data to make it easier to derive the data structure and schema using the Wrangler later on when we build the data pipeline with Data Fusion.

`gsutil cp SampleFile.csv gs://[YOUR_DATA_SOURCE_BUCKET]` where is YOUR_DATA_SOURCE_BUCKET = csv-load-raw-source  

You can see at the file content:  
`>gsutil cat -h gs://csv-load-raw-source/SampleFile.csv`  

The source files that will feed the process has the following schema:
`
id: Long  
status_code: Long  
invoice_number: Long  
item_category: String  
channel: String  
order_date: Datetime  
delivery_date: Datetime  
amount: Float  
`

There are some changes that need to be made prior to inserting the data into BigQuery, the date columns in the dataset are in the format dd-MM-yyyy H:mm and will need to be parsed to yyyy-MM-dd hh:mm in order for BigQuery to insert them correctly, also, in the float column the decimal separator are commas rather than points, we will also need to replace that to be able to insert the number as a float data type in BigQuery. We’ll perform all these transformations later on in the Data Fusion pipeline.

</details>

<details>
<summary> Create the Dataset and table in BigQuery</summary>

we will use the schema as the input for creating the table in BigQuery that will hold the data.

Navigate to the BigQuery service and within you project, create a new dataset, for simplicity I named it dataset1 :

![](/images/dataset1.png)  
![](/images/dataset2.png)

Then, within the newly created dataset, I just created a simple empty table and named it table1, with the same column names as the source CSV file and accommodating the corresponding data types. So it looks like this:  
![](/images/dataset3.png)

</details>
<details>
<summary>Create the Data Fusion Instance</summary>

Enable the Cloud Data Fusion API if you haven’t done so already:  
![](/images/datafusion1.png)  

Once the API is enabled, navigate to Data Fusion in the left menu and click on CREATE AN INSTANCE:  
![](/images/datafusion2.png)  

Name your instance cdf-test-instance.  
Data Fusion leverages Cloud Dataproc as its underlying big data processing engine, this means that when a data pipeline is executed, Data Fusion spawns an ephemeral Dataproc cluster to perform the data processing for you and submits the pipeline processing to the Dataproc cluster as a spark job, once the execution of the job is finished, Data Fusion deletes the Dataproc cluster for you. Make sure to grant the service account that Data Fusion uses, the proper permissions to spawn Cloud Dataproc Clusters, it will prompt you to authorize it, when it does, click the GRANT PERMISSION button (also keep in mind the region in which the Data Fusion instance is deployed, needs to match the region in which the BigQuery dataset was created):  
![](/images/datafusion3.png)  
![](/images/datafusion4.png)  

Click on the CREATE button, the instance creation will take a few minutes.

Once the Data Fusion instance is created, copy the Service Account Data Fusion is using and grant it the “Cloud Data Fusion API Service Agent” role by navigating to IAM and clicking the +ADD button, with this role assigned to the Data Fusion Service Account, Data Fusion can access data from/to other services such as Cloud Storage, BigQuery and Dataproc:  
![](/images/datafusion5.png)  
![](/images/datafusion6.png)  
![](/images/datafusion7.png)  
![](/images/datafusion8.png)  

Now that the instance is created and we made sure the Service Account that Data Fusion uses has the required permissions, we’re ready to create the data transformation pipeline that will take the CSV source file, it will perform some transformations on it and it will load the data to table in BigQuery we created earlier.
</details>

<details>
<summary>Create the data pipeline in Data Fusion</summary>

In the Data Fusion section you’ll see the Data Fusion instance, click on the View instance link to access the Data Fusion UI:  
![](/images/datapipeline1.png)  
The Data Fusion UI will be opened in another tab on your browser:  
![](/images/datapipeline2.png)

We will begin designing the pipeline from scratch for clarity, so click in the Studio link under the Integrate card  
![](/images/datapipeline3.png)

You will be redirected to the studio page, first, give the pipeline a meaningful name in the top center of the screen (you will need to reference the pipeline name later on in the Cloud Function python script, when the Cloud Function references it to get the execution started):  
![](/images/datapipeline4.png)

Next, we will read the sample CSV file, we will just pass through the whole file to the next stage, and will parse the CSV in the following step.  
![](/images/datapipeline5.png)

Hover your mouse over the green GCS box that was added to the canvas when you clicked the GCS icon on the left menu. A “properties” button will appear, click on this button.  
![](/images/datapipeline6.png)  

In the properties page of the GCS source component, set the “Path” property to: gs://[YOUR_DATA_SOURCE_BUCKET]/${FileName}  (YOUR_DATA_SOURCE_BUCKET = csv-load-raw-source)

Where ${FileName} acts as a Runtime Argument variable that will be passed to the pipeline at execution time (we will define the variable later on as part of the pipeline’s metadata).

In the output schema section to the right, delete the offset field so that it does not get passed through to the next step in the pipeline, and only the body of the text gets passed on to the data wrangler component we will set up in the next step of the pipeline.


</details>


## Cost Consideration

### Assumptions
Region for services is North America (us-east1)

|	Services|								Pricing options|								Cost|
|--|--|--|
|Cloud Storage|		(per GB per Month)  								$0.020|			~$0.020	|
|Cloud Functions|		512MB Memory	.333 vCPU|  	$0.000000925 (Price/100ms)|     ~2
|Cloud Data Fusion| 	(Developer edition, Price per instance per hour) 	$0.35|			~$3.5  (10h)|
|BigQuery|			(Standard Edition, slot hour)						$0.04 	|		~$4|
|Data Studio|			free?| |

Overall costs approximately expected around $10-15



 ## Reference

 Article with solution https://medium.com/google-cloud/from-zero-to-hero-end-to-end-automated-analytics-workload-using-cloud-functions-data-fusion-28670e5e7c74
