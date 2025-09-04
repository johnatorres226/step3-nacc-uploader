Context
This project is git clone from a python uploader that uses pants buils and docker, and needs to be adjusted to 
use pyproject.toml, venv, and work primarily in windows. Hence, we are removing any documentation on pants/dockers 
and their dependency management hinted in this project. 

This project needs to be adjusted to a new structure. 

CLI
The cli needs to be standarized in the cli.py file.
CLI name: udsv4-nacc-uploader [command] [options]
Commands:
--upload
--fetcher
--pull-errors
--pull-identifiers
--pull-status
--packet-finalization
--help

The upload command will handle the fetching the REDCap report, transforming it into a CSV file, and uploading it to FLYWHEEL.
It will also output the necessary logs in the comprehensive log and backup log files. Additiaonlly, it will output the json file
to upload to REDCap after the FLYWHEEL upload process is complete. Hence the optional commands will be: 
--upload ["flywheel", "redcap"] [options --initials TEXT this will be used for the log file]
--upload flywheel [options --initials TEXT this will be used for the log file]
--upload redcap [options --initials TEXT this will be used for the log files and the REDCap variables]

Other options for upload:
--mode ["all", "batch", "single"] with the default being all. This will be filtering logic for the upload process.
This will go into the fetcher.py file to determine how the data is fetched and processed. The fetcher pull a report, 
and such report will then be filter by the mode selected.
if --mode all is default method to pull the report and no aditioanl filtering will be done.
if --mode batch then the user will pass a list of ptids to pull, and the report will be filtered by those ptids.
For --mode batch and single the user will pass --ptid [TEXT, TEXT, TEXT] for single --ptid TEXT

Commands:
--upload flywheel --initials TEXT --mode ["all", "batch", "single"] --ptid [TEXT, TEXT, TEXT]
--upload redcap --initials TEXT --mode ["all", "batch", "single"] --ptid [TEXT, TEXT, TEXT]

Additional commands:
--data-flywheel [PATH] this will be the data file path for the FLYWHEEL upload process.
--data-redcap [PATH] this will be the data file path for the REDCap upload process.
--output [PATH] this will be the output content that the were the user wants the output files to be saved.
--test this commmand will be used to test the upload process without actually uploading the data to the ingest pipeline,
this will use the sandbox pipeline in FLYWHEEL and will not be used for the REDCap upload process.

Currently the project makes use of the following commands:
--pipeline ["sandbox", "ingest"]  which is a flywheel command to test the upload (sandbox) or formally upload the data (ingest)
--adcid TEXT will be continue to be used to pass the site ADRC ID
--datatype ["dicom", "enrollment", "form"] with default being form
These will be kept and used in the upload process as these are part of the uploader.py

The reupload command will handle the reuploading of the data to FLYWHEEL and REDCap and can only be done for --mode [batch|single]
and will not be compatible with --mode all. This will filter the report by the ptids provided, and will reupload them to FLYWHEEL, 
and upload new variables values in REDCAP. 

Defaults will run for mode all, and will not require the list or ptid options.
--upload flywheel --initials TEXT --pipeline ["sandbox", "ingest"] --adcid TEXT --datatype ["dicom", "enrollment", "form"]
--upload redcap --initials TEXT

The full-upload command will do both the FLYWHEEL upload and the REDCap upload in one go - and end-to-end process.
The commands should follow the context in the demo folder for each of the respective commands.
The options for each of the commands should also follow the context in the demo folder. They should
all have a --help option that provides information on the command and its options.
Lastly, this project already contains commands options for the other processes, which
will be kept but just adapted and centralized in the cli.py file.

Test run or Pre Upload Run
Before uploaing the data to FLYWHEEL, we will run a --test check to ensure that the data is ready for upload. This will help verify
if needed. Currenlty, there are instances when a record is uploaded and errors are found and it needs to be reuploaded. Under these circumtances,
once the error has been corrected, we would like to check that the prior upload and the new upload are not the same ensuring the results are 
capture. The command --test --initials TEXT --mode [all|batch|single] --ptid TEXT the default
command will be 
Full command:
--upload flywheel --test --initials TEXT --pipeline sandbox" --adcid TEXT --datatype form
This will run a check on the data to ensure that the data is ready for upload.

These commands will not use the upload command options, and will only perseve the options already provided
in the current documention: 
--pull-errors
--pull-identifiers
--pull-status
--packet-finalization
And their output should be to the output directory create a new subfolder with the convention: NACC_{command used e.g. ERRORS, IDENTIFIERS, STATUS}_{date in DDMMYYYY}_{timestamp in HHMMSS}.

Fetcher
Additioanlly, we will be pulling data form REDCap via a fetcher.py file. We will be fetching a specific report from
REDCap which we will transform into a CSV file and upload via API via FLYWHEEL. The documention for REDCAP
report pulling is in the REDCAP_REPORT_PULL.md file. 
The ouput of this data should follow this convention: REDCAP_NACC_UPLOAD_REPORT_{date in DDMMYYYY}_{timestamp in HHMMSS}.csv

Data Processor
The data processor will make use of the fetcher.py to create a data folder create a new subfolder with convetion: NACC_UPLOAD_{date in DDMMYYYY}_{timestamp in HHMMSS}. 
The data processor will also handle any transformations needed for the data before it is uploaded to FLYWHEEL. 
Additinally, this processor will output a json file for the uploader.py file to use to update the status of the records being uploaded. 
The json file should follow the convention: NACC_UPLOAD_{date in DDMMYYYY}_{timestamp in HHMMSS}_status.json. 
After processing the data it will create two output files for further processing:
1. csv for the FLYWHEEL python-uploader which will be created in the data file
2. json file for REDCap upload which will be in the directory: .\redcap-upload-ready-data

The data processor will specifically run the following checks if any of the following variables empty:
- nacc_upload_by_initals
- nacc_upload_date (YYYY-MM-DD format)
- packet_finalization_date
- nacc_upload_status_complete

If these variables are empty, this is an initial upload and these variables values will be updated via the REDCAP upload process
where nacc_upload_by_initals will be the initials provided in the CLI, nacc_upload_date will be the current date in YYYY-MM-DD format.
nacc_upload_status_complete will be set to 1. 

If these variables are not empty, we have to check if are either (one or other)
- nacc_finalization_status = 0
- nacc_finalization_status_2 = 0
- reupload_status=1
This means this record needs to be reuploaded and its ready to be reuploaded.

Once, intial and reuplaod checks have been done, a copy of the list of records will be created in the data directory
with the convention: NACC_READYRECORDS_{date in DDMMYYYY}_{timestamp in HHMMSS}.csv. This will help track the records
and validate any the processing. 

After the inital checks are complete, the following columns will be removed in order to uploaded:
- redcap_event_name 
- nacc_upload_by_initals
- nacc_upload_date (YYYY-MM-DD format)
- nacc_finalization_status
- reupload_status
- nacc_finalization_status_2
- packet_finalization_date
- nacc_upload_status_complete
These variables are to be removed and from the dataset after the checks have been done, and before the upload to FLYWHEEL.

Uploader
There are two upload processes in this project. The first the FLYWHEEL upload process which is done by the python-uploader directory. 
The second is a REDCap upload process which will be done after the FLYWHEEL upload process, and will be done using json file.

The intial uploader being the flywheel uploader get the final dataset from the data processor, and will upload it to FLYWHEEL.
After upload, we then need to update the REDCap upload status variables for the uploaded records. This process is still in development,
but we enter an ensamble to the REDCap upload process for later development.

These will be the variables associated with the REDCap upload process to be updated in the upload process guided by their ptid (record ID):
- nacc_upload_by_initals = passed initials in the CLI
- nacc_upload_date (YYYY-MM-DD format) = current date of run in YYYY-MM-DD format
- nacc_finalization_status 
- reupload_status
- nacc_finalization_status_2
- packet_finalization_date
- nacc_upload_status_complete

Pending Development
--upload full-upload
This command will later be added as the redcap upload is still in development.

The redcap upload will use the --packet-finalization and --pull-error commands and logical processing to update the ptid status in REDCap.
At this moment, we don't have a clear understanding of --packet-finalization and --pull-error commands and their output to complete this process. 
Hence, current the focus will be on the FLYWHEEL upload process, and the REDCap upload process will be developed later.

The Flywheel upload process will be the primary focus of this project, and the REDCap upload process will be developed later.


REDCap Upload Process
this will be the variables to be created:
1. ptid
2. redcap_event_name
3. nacc_upload_by_initals
4. nacc_upload_date (YYYY-MM-DD format)
5. nacc_upload_status_complete
6. nacc_reupload_date (YYYY-MM-DD format)
7. nacc_reupload_date_2 (YYYY-MM-DD format)

Logging
We will use a logging.py file to handle the logging mechanism. This will be used for the CLI interface. 
The logging of changes will be the data streamed via upload/fetching processes, and will be written to a log file.
Every iterarion will also written in to a comprehensive log file which will serve as the primary tracker.
This tracker will determine inital upload for QC status data, and for the Query Resolution Data. A copy of this
log will be saved in the BACKUP_LOG_PATH directory. The main copy of the log will be in logs diretory within this project,
and it will be json format and called UPLOAD_LOG_COMPREHENSIVE.json. Initial will be required in the CLI and it will be used
to piped into the log files and into the data proccessor for the REDCap upload process.

Conventions:
- date stamp format: DDMMMYYYY
- timestamp format: HHMMSS
- file names should be in uppercase for the first letter only, and use underscores for spaces
- coding conventions should follow PEP 8 guidelines

Reformatting
This project current has a lot of documentation on processes that will no be used and need to be updated. Additionally, 
this project uses outside material from https://github.com/naccdata/data-platform-demos and the licese within the project is the same
as this is a clone repo. Hence the materials here need to be referenced. 

Workflow
The workflow for this project will be as follows:
1. Fetch current data from REDCap project using fetcher.py.
2. Process the fetched data using data_processor.py to create a structured output.
3. Upload the processed data to FLYWHEEL using uploader.py.
4. Log the changes made during the upload process using logging.py.
5. Ensure that the CLI interface is standardized and provides clear options for users to interact with the project.
- The output of the fetcher should be a CSV file with the convention: REDCAP_NACC_UPLOAD_REPORT_{date in DDMMYYYY}_{timestamp in HHMMSS}.csv
- 