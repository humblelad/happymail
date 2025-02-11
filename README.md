# Happymail
<img src="https://github.com/humblelad/happymail/blob/main/images/happymail.jpg"  width="150" height="100">


Convert your job rejection emails to motivational emails on the fly!

## Architecture Diagram
<img src="https://github.com/humblelad/happymail/blob/main/images/arch.jpg"  width="500" height="400">

To Do:
- In depth Docs
- Terraform script to auto deploy

  I have added some docs although i am aware more details work is pending, but I am trying to have the auto deploy setup ready via terraform scripts eventually.

## Prequisites:
1. Setup 0auth client creds in GCP:
   AUTHRIOZED Redirect uri as http://localhost:8080/
2. Scope

   ![Screenshot 2025-02-11 at 12 10 17 PM](https://github.com/user-attachments/assets/0703a7b9-61a8-46b0-aaad-90c614c652d6)
3. I put publishing status as testing and so the 0auth token may expire in 7 days.
4. Download the credentials.json file
5. Go to gmail settings and then add a new label like "rejected mails".
6. After this we need to create a filter with certain keywords like below and apply them to the label.
    ![Screenshot 2025-02-11 at 12 20 51 PM](https://github.com/user-attachments/assets/46c7aae2-1e48-4e11-bc90-ad8d88debf98)
7. It is very important to figure out the labelId of the label. We will do that in the next section.

## Generate token.pickle locally

Use the auth.py script to generate token.pickle

## Figure out the labelid
Run the script label_id.py and find the labelid of the label and modify the scripts to use that. ( Otherwise scripts won't work)



## GCP bucket

Create a GCS bucket and upload this token.pickle file there as well as an empty file named prev_history_id.txt



## CLoud run functions

There are 2 CR func running for the project. One is to update the historyid ? So what is this historyid ?

For example the prev history id is 7 and the new history id is 10, we are able to deduce grab all the messageid( emails) in b/w them. In short deduce that new mails have come. 

This writing of the historyid is done by happymail_watcher.py CR function to GCS bucket.

### Use Cloud scheduler to run it as cron every 6 days because this watching gets expired every 7 days so we need to keep on refreshing it.

0 0 */6 * *

### main.py : 
This is the main cloud run function which should be run.
This cloud run function would be triggeed via cloud pub sub trigger whenever a new mail is recieved in the lable we just set. This saves cost for us otherwise the function would run for each and every new mails which is not good :) . THis is was difficult to figure out but is possible via 'labelFilterBehavior': 'include' 

Create a pub sub event including topic and subscription and the delivery type should be PUSH towards the cloud run funcion.
![Screenshot 2025-02-11 at 12 38 52 PM](https://github.com/user-attachments/assets/48119318-7ce1-48a3-901b-f51f8fcde335)

## Important
Ensure you give necessary IAM permissions to the service account Default compute service account which is the default one which runs both the cloudn run functions.

![Screenshot 2025-02-11 at 12 42 30 PM](https://github.com/user-attachments/assets/42a9b9d4-e03f-4331-87f4-515d7d03e38b)
