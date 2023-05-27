# pip install tweepy boto3 lxml requests pytz flask

from flask import Flask
import tweepy
import html
from lxml import etree
import requests
import lxml.html
import boto3
import csv
from datetime import datetime
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from os.path import exists
import pytz
from foo.secrets import *



headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
    }

app = Flask(__name__)
s3 = boto3.client('s3')

def scrapeBills():
    timeZ_Ny = pytz.timezone('America/New_York')
    timeNow = datetime.now(timeZ_Ny).strftime('%Y-%m-%d %H:%M:%S')
    print('timeNow:', timeNow)

    s = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
    s.mount('http://', HTTPAdapter(max_retries=retries))

    legislationAdded = False

    legistar_url = "https://cityofcleveland.legistar.com/Feed.ashx?M=L&ID=12150185&GUID=3fa9f6f4-3f6a-48d3-83ce-0d9f3bbd8669"
    r = s.get(legistar_url, headers=headers)
    root = etree.XML(r.text.encode())
    items = root.xpath('//rss/channel/item')

    replacementText = [ "AN EMERGENCY ORDINANCE ", "AN EMERGENCY RESOLUTION ", "AN ORDINANCE ", "A RESOLUTION ", "Title: ", 'To supplement the Codified Ordinances of Cleveland, Ohio, 1976, by ', 'To supplement the Codified Ordinances of Cleveland, Ohio 1976, by ', ' of the Codified Ordinances of Cleveland, Ohio, 1976' ]


    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    # calling the api
    api = tweepy.API(auth)

    previous_tweets = []
    deleted_legislation = []
    skip_deleted_alerts = []
    previous_tweet_urls = []

    for tw_status in api.user_timeline(count=200, tweet_mode='extended'):
        if 'City Council removed ' not in html.unescape(tw_status.full_text):
            billId = html.unescape(tw_status.full_text).split(':')[0].split(',')[0]
            previous_tweets.append(billId)
            previous_tweet_urls.append(tw_status.entities['urls'][0]['expanded_url'])

            # This call to check for urls will fail if a tweet doesn't have a URL linked, such as ordinary retweets
            resp = s.head(tw_status.entities['urls'][0]['expanded_url'])

            # sometimes Legistar will not include a 'Content-Length' header, but instead a 'Transfer-Encoding': 'chunked' header
            if 'Content-Length' in resp.headers.keys():
                print(billId, resp.headers['Content-Length'])

            # When the link is broken after an item is removed from Legistar, the url will return a specific content length of 136.
            # We'll use this to find deleted items.
            if 'Content-Length' in resp.headers.keys() and int(resp.headers['Content-Length']) == 136:
                if tw_status.id not in skip_deleted_alerts:
                    print('TWEET THAT ITEM IS DELETED')
                    deleted_legislation.append({'in_reply_to_status_id': tw_status.id, 'text': 'City Council removed '+ billId + ' from Legistar, and the item link is now broken. Sometimes Council posts items before they were ready for sharing publicly. You\'ll find a new tweet if Council reposts the item on Legistar!'})
                else:
                    print("WE'VE ALREADY TWEETED THE DELETE ALERT", tw_status.id)


    # DO SOMETHING FOR DELETED LEGISLATION
        else: # if "City Council removed" is in the tweet text
            #print(tw_status)
            skip_deleted_alerts.append(tw_status.in_reply_to_status_id)
            pass


    print("Deleted legislation:", deleted_legislation)

    for delete_alert in deleted_legislation:
        api.update_status(status = delete_alert['text'], in_reply_to_status_id = delete_alert['in_reply_to_status_id'] , auto_populate_reply_metadata=True)
        print('TWEETED: ', delete_alert['text'])


    for item in items[::-1]:

        bill = {}
        bill['dept_req'] = False
        bill['title'] = item.xpath('.//title')[0].text
        print('title',bill['title'])
        bill['link'] = item.xpath('.//link')[0].text.replace('From=RSS&','').replace('Gateway.aspx','LegislationDetail.aspx').replace('M=LD&','')
        bill['description'] = item.xpath('.//description')[0].text.replace("  "," ")
        bill['category'] = item.xpath('.//category')[0].text
        bill['pubDate'] = item.xpath('.//pubDate')[0].text

        for text in replacementText:
            bill['description'] = bill['description'].replace(text, '')

        bill['description'] = bill['description'].replace(',,',',').replace(', ,',',').replace("  "," ")
        bill['description'] = bill['description'][:1].upper() + bill['description'][1:]


        if bill['title'] not in previous_tweets or (bill['link'] not in previous_tweet_urls):
            # This file is only for further research. You can comment out the next 7 lines if you just want to tweet.
            if not exists('/tmp/timestamped-legistar_tweets.csv'):
                try:
                    s3.download_file(s3bucket, 'timestamped-legistar_tweets.csv', '/tmp/timestamped-legistar_tweets.csv') # DEBUGGIN
                except:
                    pass

            f = open('/tmp/timestamped-legistar_tweets.csv', mode='a')
            csv_writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)

            # Download legislation info
            r = s.get(bill['link'], headers=headers)
            doc = lxml.html.document_fromstring(r.text)

            sponsors = ''
            sponsorString = ''
            leadSponsorFull = ''
            try:
                bill['sponsors'] = doc.xpath('//*[@id="ctl00_ContentPlaceHolder1_lblSponsors2"]')[0].text_content()
                leadSponsorFull = bill['sponsors'].split(',')[0].strip()
                if "By Departmental Request" in bill['sponsors']:
                    bill['dept_req'] = True
                else:
                    sponsors = bill['sponsors'].split(',')
                    if 'Jones' in sponsors[0]:
                        leadSponsor = sponsors[0][0]+'. '+sponsors[0].split(' ')[-1]
                    else:
                        leadSponsor = sponsors[0].split(' ')[-1]
                    numOtherSponsors = len(sponsors) - 1

                    if numOtherSponsors > 0:
                        sponsorString = ", "+leadSponsor + "+" + str(numOtherSponsors)
                    else:
                        sponsorString = ", "+leadSponsor
            except:
                bill['sponsors'] = ''

            #try:
            #    attachments = doc.xpath('//span[@id="ctl00_ContentPlaceHolder1_lblAttachments2"]/a')
            #    #print(attachments)
            #except:
            #    attachments = ''

            tweet = bill['title'] + sponsorString + ": " + bill['description']
            if len(tweet) > 256:
                tweet = tweet[0:252] + "..."

            tweet = tweet + " " + bill['link']
            print(tweet)

            api.update_status(tweet)
            previous_tweets.append(tweet.split(':')[0].split(',')[0])
            print('TWEETED!')

            # This file is only for further research. You can comment out the next 2 lines if you just want to tweet.
            csv_writer.writerow([bill['title'], bill['category'], leadSponsorFull, bill['description'], bill['link'], timeNow])
            f.close()

            legislationAdded = True
        else:
            print('ALREADY TWEETED!')


    # This file is only for further research. You can comment out the next 3 lines if you just want to tweet.
    if legislationAdded:
        with open('/tmp/timestamped-legistar_tweets.csv', "rb") as f:
            s3.upload_fileobj(f, s3bucket, 'timestamped-legistar_tweets.csv')
        os.remove('/tmp/timestamped-legistar_tweets.csv')



if __name__ == "__main__":
    scrapeBills()
