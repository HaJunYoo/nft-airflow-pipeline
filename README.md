<aside>
ð¡ (https://api.opensea.io/api) ì apië¥¼ ì´ì©í´ì ë°ì´í° íì´íë¼ì¸ì ETL ì ì¥ì í´ë³´ë íë¡ì í¸

</aside>

1. íì´ë¸ ìì±
     
    ```python
    from datetime import datetime
    import json
    
    from airflow import DAG
    from airflow.providers.sqlite.operators.sqlite import SqliteOperator
    
    default_args = {
      'start_date': datetime(2023, 1, 1),
    }
    
    # DAG Skeleton 
    with DAG(dag_id='nft-pipeline',
             schedule_interval='@daily', # ì£¼ê¸° ì§ì 
             default_args=default_args, 
             tags=['nft'],
             catchup=False) as dag:
      pass
      
      creating_table = SqliteOperator(
        task_id='creating_table',
        sqlite_conn_id='db_sqlite',
        # if not exists ì¬ì©
        sql='''
          CREATE TABLE IF NOT EXISTS nfts (
            token_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            image_url TEXT NOT NULL
          )
        '''
      )
    ```
    
    - airflow íì¤í¬ ì¤í - `2023-02-20`(execution date)
        
        `airflow tasks test nft-pipeline creating_table 2023-02-20`
        
        â INFO - Marking task as SUCCESS. dag_id=nft-pipeline, task_id=creating_table, execution_date=20230220T000000, start_date=, end_date=20230221T151044 
        
2. API íì¸
     
    ```python
    from airflow.providers.http.sensors.http import HttpSensor
    
    is_api_available = HttpSensor(
        task_id='is_api_available',
        http_conn_id='opensea_api',
        endpoint='api/v1/assets?collection=doodles-official&limit=1'
      )
    ```
    
3. NFT ì ë³´ ì¶ì¶
    
    [https://api.opensea.io/api/v1/assets?collection=doodles-official&limit=1](https://api.opensea.io/api/v1/assets?collection=doodles-official&limit=1)
    ìì SimpleHttpOperator****************ë¥¼ íµí´**************** api ë´ì©ì ê°ì ¸ì¬ ê²ì´ë¤.
     
    ```python
    extract_nft = SimpleHttpOperator(
        task_id='extract_nft',
        http_conn_id='opensea_api',
        endpoint='api/v1/assets?collection=doodles-official&limit=1',
        method='GET',
        response_filter=lambda res: json.loads(res.text),
        log_response=True
      )
    ```
    
4. NFT ì ë³´ ê°ê³µ
    
    `SimpleHttpOperator` ë¡ ê°ì ¸ì¨ ì ë³´ë¥¼ ê°ê³µíë task
    
    ë°ì´í°ê° ëì´ì¤ê² íë ¤ë©´ `xcom_pull`ì ì¬ì©
    
    ```python
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
    
    ## call python processing function
      process_nft = PythonOperator(
        task_id='process_nft',
        python_callable=_processing_nft
      )
    ```
    
5. NFT ì ë³´ ì ì¥
    
    `BashOperator` ë¥¼ ì´ì©í´ì bash ì»¤ë§¨ëë¥¼ íµí´ ì¶ì¶í csv ë°ì´í°ë¥¼ sqlite dbì ì ì¥íë¤
    
    ```python
    storing_user = BashOperator(
        task_id='storing_user',
        bash_command='echo -e ".separator ","\n.import /tmp/processed_user.csv users" | sqlite3 /Users/yoohajun/Airflow/nft.db'
      )
    ```
    
    `echo -e ".separator ","\n.import /tmp/processed_user.csv users" | sqlite3 /Users/yoohajun/Airflow/nft.db`
    
    â csv íì¼ì ìª¼ê°ì nfts ë¼ë íì´ë¸ì import íë¤ë ëªë ¹ì´
    

1. DAG ë´ task ìì¡´ì± ì£¼ì
    
    ```python
    ## DAG dependency insertion
    creating_table >> is_api_available >> extract_nft >> process_nft >> storing_user
    ```
    
    ê° íì¤í¬ì `dag` ë§¤ê° ë³ìë¥¼ ì ë¬íë©´ íì¤í¬ê° ëì¼í DAG ì¸ì¤í´ì¤ì ì°ê²°ëì´ `>>` ì°ì°ìë¥¼ ì¬ì©íì¬ ìë¡ ê´ë ¨ë  ì ììµëë¤.
    
    ë°©ë² 1.
    
    ```python
    extract_nft = SimpleHttpOperator(
      task_id='extract_nft',
      http_conn_id='opensea_api',
      endpoint='api/v1/assets?collection=doodles-official&limit=1',
      method='GET',
      response_filter=lambda res: json.loads(res.text),
      log_response=True,
      dag=dag # ì¶ê°
    )
    ```
    
    ë°©ë² 2
    
    ```python
    with DAG(dag_id='nft-pipeline',
             schedule_interval='@daily',
             default_args=default_args,
             tags=['nft'],
             catchup=False) as dag:
    ```
     

1. storing task revision
    
    ìì taskë ì ì¥ì í  ë, token idê° ì¤ë³µëë©´ ì ì¥ì´ ëì§ ìëë¤
    
    ì´ë¯¸ ì ì¥ë rowê° ì¤ë³µë  ì ì ì¥ì íì§ ìê³  echoë¥¼ íµí´ íì¶ë¬¸ì ì¶ë ¥íëë¡ íë¤.
    
    ```python
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
    ```
    
2. Backfill ë¬¸ì 
    
    ë§¤ì¼ ì£¼ê¸°ì ì¼ë¡ ëìê°ë íì´íë¼ì¸ì ë©ì·ë¤ê° ëª ì¼ ë¤ì ì¤íìí¤ë©´ ì´ë»ê² ë ê¹?
    
    DAG ì¤ì¼ë í¤ ë´ì catch up íë¼ë¯¸í°ë¥¼ íµí´ ì¡°ì í  ì ìë¤.
    
    start dateë¶í° backfillì ì¤íí  ê²ì´ë¤.
    
    ë§ì§ë§ì¼ë¡ ëë¦¬ì§ ëª»íë dagë¶í° backfillì ìë â ë°ë ¸ë ëª ê°ì DAGë¥¼ íì ë£ì´ ì¤íí  ê²ì´ë¤.
