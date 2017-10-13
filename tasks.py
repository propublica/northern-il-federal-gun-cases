import csv
import os
import requests


from bs4 import BeautifulSoup
from datetime import date
from invoke import task
from juriscraper.pacer.http import PacerSession
from juriscraper.pacer import DocketReport
from random import randint


@task
def fetch(ctx, overwrite=False):
    print('fetch')
    session = PacerSession(username=os.environ.get('PACER_USERNAME'), password=os.environ.get('PACER_PASSWORD'))
    today = date.today().strftime('%m/%d/%Y')
    citations = [
                    '18:922A.F',
                    '18:922C.F',
                    '18:922E.F',
                    '18:922G.F',
                    '18:924A.F',
                    '18:924C.F',
                ]
    for citation in citations:
        outputfile = 'data/{0}.tsv'.format(citation)

        if overwrite or not os.path.exists(outputfile):
            body = {
                "office": (None, ""),
                "case_type": (None, ""),
                "case_flags": (None, ""),
                "citation": (None, citation),
                "pending_citations": (None, "1"),
                "terminated_citations": (None, "1"),
                "cvbcases": (None, "No"),
                "filed_from": (None, "1/1/2007"),
                "filed_to": (None, today),
                "terminal_digit": (None, ""),
                "pending_defendants": (None, "on"),
                "terminated_defendants": (None, "on"),
                "fugitive_defendants": (None, ""),
                "nonfugitive_defendants": (None, "1"),
                "reportable_cases": (None, "1"),
                "non_reportable_cases": (None, "1"),
                "sort1": (None, "case number"),
                "sort2": (None, ""),
                "sort3": (None, ""),
                "format": (None, "data")
            }
            intermediate_resp = session.post('https://ecf.ilnd.uscourts.gov/cgi-bin/CrCaseFiled-Rpt.pl?1-L_1_0-1'.format(randint(200000, 40000000)), files=body)

            intermediate_doc = BeautifulSoup(intermediate_resp.content, 'lxml')
            form = intermediate_doc.find('form')
            action = form.attrs.get('action')
            action_path = action.split('/')[-1]
            url = 'https://ecf.ilnd.uscourts.gov/cgi-bin/' + action_path

            resp = session.post(url)

            print('-'*50)
            print(citation)
            print('-'*50)
            print(resp.content)

            with open(outputfile, 'w') as f:
                f.write(resp.content)

        else:
            print('skipped {0}'.format(citation))


@task
def clean(ctx):
    data = []

    for filename in os.listdir('data'):
        charges, ext = filename.rsplit('.', 1)
        fullpath = os.path.realpath(os.path.join('data', filename))
        with open(fullpath) as f:
            reader = csv.DictReader(f, delimiter='|')
            rows = list(reader)
            for row in rows:
                row['charges'] = charges
                for k, v in row.items():
                    row[k] = v.strip()
                if row.get('cs_case_number'):
                    data.append(row)

    with open('processed/federal-gun-cases.csv', 'w') as f:
        writer = csv.DictWriter(f, fieldnames=sorted(data[0].keys()))
        writer.writeheader()
        for row in data:
            writer.writerow(row)


@task
def sync(ctx):
    ctx.run('aws s3 sync image s3://assets.propublica.org/illinois/2017-10-13-federal-gun-cases --acl public-read --cache-control max-age=30')
