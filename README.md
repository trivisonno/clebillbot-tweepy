This is the code that runs the @CleBillBot twitter acccount. This README assumes some familiarity with AWS, Lambda, S3, and Python.

Flask is used to create and deploy the application to Amazon's Lambda and API platforms.
Tweepy is used to interact with Twitter's platform via python.
Boto3 is necessary if you want to use the S3 file saving system (the info for every legislative item is also saved to a CSV file for further analysis, but it not necessary for the Twitter functions; in the code you'll see where you can comment out certain lines).
Requests allow python to connect with websites and download data.
LXML is a python parser of XML and HTML code.
Pytz is used for timezone control (this app is for Cleveland so we're -0500).

Your Twitter bot API keys are stored in the foo/secrets.py file. Rename the foo/secrets.sample.py to foo/secrets.py and add your four key tokens you are given from the Twitter Developer dashboard. (There are many guides online explaining how to set up a Twitter bot account and handle.)

Also ensure that your zappa_settings.json file includes all of the keys contained in the zappa_settings.sample.json file in this repo.

This script can be deployed with zappa. To set it up on your own computer, first install zappa:
```pip install zappa```

Then install all the script dependencies:
```pip install tweepy boto3 lxml requests pytz flask```

You can then deploy to Amazon AWS:
```zappa deploy dev``` to deploy your code the very first time, and  
```zappa update dev``` to push updates to your deployment.
