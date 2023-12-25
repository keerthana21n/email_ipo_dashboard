import os
import re
import sys
import pandas 
import numpy as np
import smtplib
import requests
import traceback

from io import StringIO
from tkinter import *
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import chittorgarh_configs as CC

extra_headers = ['P/E Multiples','Buy or Not','Description','GMP (Rs)','Subscription(times) - Retail','SPTulsian Review','Apply Date', 'GMP Link', 'SPT Link']
headers_not_required = ['Issue Size (Rs Cr.)','Lot Size','Exchange']

def notify(title, text):
    os.system("""osascript -e 'display notification "{}" with title "{}"'""".format(text, title))

def fetch_url_contents(url = CC.MAINBOARD_URL):
    req = requests.get(url)
    content = str(BeautifulSoup(req.content,"html5lib"))
    return content

def make_table(content):
    content = content.replace('\n','')
    heading_string = re.findall(f'<tr><th class="text-center">.*?</th></tr>', content)[0]

    headings_unformatted  = re.findall(">.*?<", heading_string)
    headings = []

    for heading in headings_unformatted:
        if heading != '><':
            headings.append(heading[1:-1])
    
    headings.pop()
    headings.append('IPO Link')

    ipo_list_unformatted = []
    for colour in CC.UPCOMING_IPOS_COLOUR:
        ipo_colour_list = re.findall(f'<tr class="{colour}"><td>.*?</td></tr>', content)
        ipo_list_unformatted += ipo_colour_list

    ipo_list = []
    for ipo in ipo_list_unformatted:
        ipo_contents_informatted  = re.findall(">.*?<", ipo)
        ipo_contents = []

        for ipo_content in ipo_contents_informatted:
            if ipo_content != '><':
                ipo_contents.append(ipo_content[1:-1])
        
        ipo_url = re.findall('<a href=".*?"', ipo)[0]
        ipo_contents.append(ipo_url[9:-1])

        ipo_list.append(ipo_contents)

    return headings, ipo_list

def get_ipo_details(url_contents, close_date, ipo_name, topic_id):
    print(ipo_name)
    url_contents = url_contents.replace('\n','')
    result = {
        header : '' for header in extra_headers
    }

    pe_multiples_string = re.findall('<td>P/E.*?</td>.+?<', url_contents)[0]
    result['P/E Multiples'] = re.findall('>.*?<', pe_multiples_string)[-1][1:-1]

    description_string = re.findall('<h2 class="border-bottom">About.*?</div>', url_contents)[0]
    for desc in description_string.split('<p>')[1:3]:
        result['Description'] += str(desc).replace('</p>','')

    subsrciption_times_link = f"https://www.chittorgarh.com/documents/subscription/{topic_id}/details.html"
    
    try:
        subsrciption_times_contents = fetch_url_contents(subsrciption_times_link)
        subsrciption_times_string = re.findall('The public issue subscribed .*? times in the retail category', subsrciption_times_contents)[0] 
        result['Subscription(times) - Retail'] = subsrciption_times_string[28:-29]
    except Exception as e :
        try:
            subsrciption_times_string = re.findall('>Retail</td><td class="text-end">.*?<', url_contents)[0] 
            result['Subscription(times) - Retail'] = subsrciption_times_string[33:-1]
        except Exception as e :
            print(traceback.format_exc())
            result['Subscription(times) - Retail'] = "Unavailable"

    gmp_link_string = re.findall('News</a></li><li class="nav-item"><a class="nav-link" href=".*?" target="_blank" title="IPO GMP">', url_contents)[0]
    result['GMP Link'] = re.findall('href=".*?"', gmp_link_string)[0][6:-1]

    try:
        gmp_contents = fetch_url_contents(result['GMP Link'])
        gmp_price_string = re.findall('last GMP is ₹.*?<', gmp_contents)[0]
        result['GMP (Rs)'] = re.findall('₹.*?<', gmp_price_string)[0][1:-1]
    except Exception as e :
        print(traceback.format_exc())
        result['GMP (Rs)'] = "Unavailable"

    buy_or_not = re.findall('Buy or Not</h2>.*?</table>', url_contents)[0]
    but_or_not_df = pandas.read_html(StringIO("<table " + str(buy_or_not).split("<table ")[1]), flavor='bs4')[0]
    result['Buy or Not'] = but_or_not_df.set_index('Review By').T.to_dict()
    
    result['Apply Date'] = get_apply_date(close_date)

    result['SPT Link'], result['SPTulsian Review'] = get_sptulsian_review(ipo_name)
    
    return result  

def get_apply_date(close_date):
    current_date = datetime.strptime(close_date,'%b %d, %Y')
    list_of_holidays = map(lambda date : datetime.strptime(date ,'%d-%b-%Y'), CC.HOLIDAY_LIST)
    
    while(True):
        current_date = current_date - timedelta(days = 1)
        if current_date not in list_of_holidays and current_date.strftime("%A") not in ['Saturday','Sunday']:
            break
    
    return datetime.strftime(current_date, '%b %d, %Y')

def get_sptulsian_review(ipo_name):
    try:
        contents = fetch_url_contents('https://www.sptulsian.com/f/ipo-analysis/')
        contents = contents.replace('\n','').lower()

        link = f"https://www.sptulsian.com/f/ipo-analysis/{str(ipo_name).lower().replace(' ','-')}"

        tagline_string = re.findall(f'<a class="article_content_url" href="{link}">.*?<br/>', contents)[0]
        tagline = re.findall("<div>.*?<br/>", tagline_string)[0][5:-5]
        return link, str(tagline).title().strip()

    except Exception as e:
        print(traceback.format_exc())
        return "No Link Found", "No Review Found"

def format_to_html(dataframe : pandas.DataFrame):
    html = "<html>"

    if len(dataframe.index) == 0:
        html += "<h2>No upcoming IPOs</h2>"
        html += "</html>"
        return html

    html += f'<p>There are {len(dataframe.index)} upcoming IPOs. Please find the details below : </p>'
    html += f'<p>Note : All the details were fetched from : <a href="{CC.MAINBOARD_URL}">{CC.MAINBOARD_URL}</a></p>'
    
    for index, row in dataframe.iterrows():
        html += f"<h2>{index}. {row['Issuer Company']}</h2>"
        html += f"<p>{row['Description']}</p>"
        
        row_df = dataframe[dataframe['Issuer Company'] == row['Issuer Company']]
        row_df = row_df.rename(columns = {'Buy or Not' : 'Buy or Not (Subscribe, Neutral, Avoid)'})
        
        html_suffix = "<br><h3>Links</h3>"
        html_suffix += "<p><ul>"
        html_suffix += f'<li>Chittorgarh IPO Link : <a href="{row["IPO Link"]}">{row["IPO Link"]}</a></li>'
        html_suffix += f'<li>Chittorgarh GMP Link : <a href="{row["GMP Link"]}">{row["GMP Link"]}</a></li>'
        html_suffix += f'<li>SP Tulsian Review : <a href="{row["SPT Link"]}">{row["SPT Link"]}</a></li>'
        html_suffix += "</ul></p>"
        
        del row_df['Description']
        del row_df['IPO Link']
        del row_df['GMP Link']
        del row_df['SPT Link']
        del row_df['Issuer Company']

        html += row_df.to_html()
        html += html_suffix

        html += "</hr>"

    html += "</html>"

    return html

def send_mail(html):
    sender = "knofficial21@gmail.com"
    recievers = ["knofficial21@gmail.com"] #["vaibhavn056@gmail.com", "knofficial21@gmail.com", "ningaraju2000@gmail.com"]
    s = smtplib.SMTP('smtp.gmail.com', 587)
    s.starttls()
    s.login(sender, "xgtk aluf ldss qodd")
    
    today = datetime.now()
    today = today.strftime("%B %d, %Y")
    msg = MIMEMultipart('alternative')
    msg["Subject"] = f"IPO Dashboard for {today}"
    msg["To"] = sender
    msg["From"] = sender
    
    part1 = MIMEText(html, 'html')
    msg.attach(part1)
    
    for reciever in recievers:
        s.sendmail(sender, reciever, msg.as_string())
    
    s.quit()

def fetch_ipo():
    content = fetch_url_contents()

    header, rows = make_table(content)

    df = pandas.DataFrame(data = rows, columns = header, index=None)
    df.index = np.arange(1, len(df) + 1)

    for header in headers_not_required:
        del df[header]

    for extra_header in extra_headers:
        df[extra_header] = ''
    
    for index, row in df.iterrows():
        url_contents = fetch_url_contents(row['IPO Link'])
        ipo_name = " ".join(str(row['Issuer Company']).split(" ")[0:-2])
        topic_id = str(row['IPO Link']).split('/')[-2]
        additional_details = get_ipo_details(url_contents, row['Close Date'], ipo_name, topic_id)
        for header in extra_headers:
            df.at[index, header] = additional_details[header]
        
        df.at[index, 'Buy or Not'] = f'Brokers : {additional_details["Buy or Not"]["Brokers"]["Subscribe"]}, {additional_details["Buy or Not"]["Brokers"]["Neutral"]}, \
                                                {additional_details["Buy or Not"]["Brokers"]["Avoid"]} \
                                       Member : {additional_details["Buy or Not"]["Members"]["Subscribe"]}, {additional_details["Buy or Not"]["Members"]["Neutral"]}, \
                                                {additional_details["Buy or Not"]["Members"]["Avoid"]}'
    
    df = df.rename(columns={"Buy or Not" : "Buy or Not (Subscribe, Neutral, Avoid)"})
    print(df.to_string())
    html = format_to_html(df)
    
    result = send_mail(html)
    notify("IPO Dashboard Email", "Success")

if __name__ == "__main__":
    try:
        fetch_ipo()
        """url = "https://www.chittorgarh.com/ipo/azad-engineering-ipo/1597/"
        contents = fetch_url_contents(url)
        with open('old_test_ipo.html','w+') as f:
            f.write(contents)
            f.close"""
        sys.exit(0)
    except Exception as e:
        print(traceback.format_exc())
        notify("IPO Dashboard Email", "Failed")
        sys.exit(1)

    

    