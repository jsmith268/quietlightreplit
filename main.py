import json
import logging
import os
import time

import pymsteams
import requests
from bs4 import BeautifulSoup
from flask import Flask
from twilio.rest import Client

logging.basicConfig(level=logging.INFO)
FROM_NUMBER = os.getenv("FROM_NUMBER")
TO_NUMBER = os.getenv("TO_NUMBER")
ENDPOINT = "https://quietlight.com/listings/"

def send_text(body_text):
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_= FROM_NUMBER,
            body=body_text,
            to= TO_NUMBER,
        )
        logging.info(message.sid)
    except Exception as e:
        logging.error(f"Error sending message: {e}")

def scrape_quietlight():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
        "Accept-Language": "en-CA,en;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-GB;q=0.6,en-US;q=0.5"
}

    try:
        resp = requests.get(ENDPOINT, headers=headers)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Error fetching data from {ENDPOINT}: {e}")
        return None

    return BeautifulSoup(resp.text, 'html.parser')

def main():

  # Replace YOUR_WEBHOOK_URL with the URL you got from Microsoft Teams
  webhook_url = os.getenv("MICROSOFT_TEAMS_WEBHOOK_URL")
  
  # Initialize the connector card object with the Microsoft Teams Webhook URL
  teams_message = pymsteams.connectorcard(webhook_url)
  

  try:  
    with open('quietlight_data.json') as json1_file:
        QUIETLIGHT_DATA = json.load(json1_file)
  except FileNotFoundError:
      print("JSON file not found")

  soup = scrape_quietlight()

  listings = soup.select('div.single-content:not(.interruption-card)')
  for listing in listings:
    
    # Process each listing...
      listing_title = listing.find('div').find('h5').getText().strip()
      listing_status = "available"
      try:
          listing_website = listing.find('div').find('a').get('href')
      except AttributeError:
          listing_website = ""
      try:
          listing_price = listing.find('div').find('div', class_="price").getText().strip()[1:]
      except AttributeError:
          listing_price = 0.00
      try:
          listing_revenue = listing.find('div').find('div', class_="revenu_sec").select('p')[0].get_text().split("$")[1].strip()
          listing_earnings = listing.find('div').find('div', class_="revenu_sec").select('p')[1].get_text().split("$")[1].strip()
      except IndexError:
          listing_revenue = ""
          listing_earnings = ""
      except AttributeError:
          listing_revenue = ""
          listing_earnings = ""
      if 'sold' in listing.get('class', []):
          listing_status = "sold"
      if 'under-loi' in listing.get('class', []):
          listing_status = "under LOI"

      # Check if listing title exists in db

      if (listing_title in QUIETLIGHT_DATA) and listing_status == "available":

          # If listing title does exist, check if price or status has changed
          if QUIETLIGHT_DATA[listing_title]["price"] != listing_price:
              # price change!
              if QUIETLIGHT_DATA[listing_title]["price"] > listing_price:
                  body_text = f"QUIET LIGHT PRICE CHANGE!!\n\nListing: {listing_title}\n\nNew Price: ${listing_price}\nOriginal Price: ${QUIETLIGHT_DATA[listing_title]['price']}"
                  send_text(body_text)
                
                  # Send Microsoft Teams Message
                  teams_message.text(body_text)
                  teams_message.send()
            
              QUIETLIGHT_DATA[listing_title]["price"] = listing_price
          if QUIETLIGHT_DATA[listing_title]["status"] != listing_status:
              # change status
              if listing_status == "available":
                  body_text = f"QUIET LIGHT STATUS CHANGE!!\n\nListing: {listing_title}\n\nNew Status: {listing_status}\nOld Status: {QUIETLIGHT_DATA[listing_title]['status']}"
                  send_text(body_text)
                
                  teams_message.text(body_text)
                  teams_message.send()
              QUIETLIGHT_DATA[listing_title]['status'] = listing_status

      # If listing title does not exist, add to the dict
      elif listing_title in QUIETLIGHT_DATA:
        pass
      else:
          body_text = f"NEW QUIET LIGHT LISTING\n\n{listing_title}\n\nLink: {listing_website}\n\nPrice: ${listing_price}\nRevenue: ${listing_revenue}\nSDE: ${listing_earnings}"
          send_text(body_text)
        
          teams_message.text(body_text)
          teams_message.send()

          print("adding listing to Quiet Light DB")
          QUIETLIGHT_DATA[listing_title] = {
              "title": listing_title,
              "url": listing_website,
              "price": listing_price,
              "revenue": listing_revenue,
              "earnings": listing_earnings,
              "status": listing_status
          }


  with open('quietlight_data.json', 'w') as fp:
      json.dump(QUIETLIGHT_DATA, fp)

def main_loop():
    
  while True:  
    main()
    print("complete")
    time.sleep(21600)


app = Flask(__name__)

@app.route('/')
def home():
    return 'Service is running'

if __name__ == "__main__":
    from threading import Thread
    
    # Run your existing main function in a separate thread
    thread = Thread(target=main_loop)
    thread.start()
    
    # Start the Flask web server
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))