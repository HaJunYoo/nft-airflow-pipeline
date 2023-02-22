from datetime import datetime
import json

from airflow import DAG
from airflow.providers.sqlite.operators.sqlite import SqliteOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from pandas import json_normalize

default_args = {
  'start_date': datetime(2023, 1, 1),
}


def _processing_nft(ti):
  assets = ti.xcom_pull(task_ids=['extract_nft'])
  if not len(assets):
    raise ValueError("assets is empty")
  nft = assets[0]['assets'][0] # nft asset

  processed_nft = json_normalize({
    'token_id': nft['token_id'],
    'name': nft['name'],
    'image_url': nft['image_url'],
  })
  processed_nft.to_csv('/tmp/processed_nft.csv', index=None, header=False)

# DAG Skeleton
with DAG(dag_id='nft-pipeline',
         # schedule_interval='@daily', # 주기 지정
         schedule_interval='* */1 * * *', # 주기 지정
         default_args=default_args,
         tags=['nft'],
         catchup=False
         ) as dag:

  creating_table = SqliteOperator(
    task_id='creating_table',
    sqlite_conn_id='db_sqlite',
    # if not exists 사용
    sql='''
      CREATE TABLE IF NOT EXISTS nfts (
        token_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        image_url TEXT NOT NULL
      )
    '''
  )

  is_api_available = HttpSensor(
    task_id='is_api_available',
    http_conn_id='opensea_api',
    endpoint='api/v1/assets?collection=doodles-official&limit=1'
  )

  extract_nft = SimpleHttpOperator(
    task_id='extract_nft',
    http_conn_id='opensea_api',
    endpoint='api/v1/assets?collection=doodles-official&limit=1',
    method='GET',
    response_filter=lambda res: json.loads(res.text), # json 형태로 변환
    log_response=True
  )

  ## call python processing function
  process_nft = PythonOperator(
    task_id='process_nft',
    python_callable=_processing_nft
  )

  storing_user = BashOperator(
    task_id='storing_user',
    bash_command='''\
      if [ "$(sqlite3 /Users/yoohajun/Airflow/nft.db "SELECT COUNT(*) FROM nfts WHERE token_id='{{ ti.xcom_pull(task_ids='process_nft')['token_id'] }}'")" -eq 0 ]; then \
        echo -e ".separator ','\n.import /tmp/processed_nft.csv nfts" | sqlite3 /Users/yoohajun/Airflow/nft.db; \
      else \
        echo "Token ID {{ ti.xcom_pull(task_ids='process_nft')['token_id'] }} already exists in nfts table"; \
      fi
    '''
  )

  ## DAG dependency insertion
  creating_table >> is_api_available >> extract_nft >> process_nft >> storing_user