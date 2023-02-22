<aside>
💡 [https://api.opensea.io/api](https://api.opensea.io/api) 의 api를 이용해서 데이터 파이프라인에 ETL 저장을 해보는 프로젝트

</aside>

1. 테이블 생성
    
    ![스크린샷 2023-02-22 오전 12.06.29.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/17ac1ad2-d64f-4ffa-bfb5-0440e8dc210d/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2023-02-22_%E1%84%8B%E1%85%A9%E1%84%8C%E1%85%A5%E1%86%AB_12.06.29.png)
    
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
             schedule_interval='@daily', # 주기 지정
             default_args=default_args, 
             tags=['nft'],
             catchup=False) as dag:
      pass
      
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
    ```
    
    - airflow 태스크 실행 - `2023-02-20`(execution date)
        
        `airflow tasks test nft-pipeline creating_table 2023-02-20`
        
        ⇒ INFO - Marking task as SUCCESS. dag_id=nft-pipeline, task_id=creating_table, execution_date=20230220T000000, start_date=, end_date=20230221T151044 
        
2. API 확인
    
    ![스크린샷 2023-02-22 오전 12.55.10.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/4b9806a6-36b4-4c5b-8651-2698b1c39f4d/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2023-02-22_%E1%84%8B%E1%85%A9%E1%84%8C%E1%85%A5%E1%86%AB_12.55.10.png)
    
    ```python
    from airflow.providers.http.sensors.http import HttpSensor
    
    is_api_available = HttpSensor(
        task_id='is_api_available',
        http_conn_id='opensea_api',
        endpoint='api/v1/assets?collection=doodles-official&limit=1'
      )
    ```
    
3. NFT 정보 추출
    
    [https://api.opensea.io/api/v1/assets?collection=doodles-official&limit=1](https://api.opensea.io/api/v1/assets?collection=doodles-official&limit=1)
    위의 SimpleHttpOperator****************를 통해**************** api 내용을 가져올 것이다.
    
    ![스크린샷 2023-02-22 오후 3.50.17.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/c8003708-1f7d-4013-9795-680433283fed/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2023-02-22_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_3.50.17.png)
    
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
    
4. NFT 정보 가공
    
    `SimpleHttpOperator` 로 가져온 정보를 가공하는 task
    
    데이터가 넘어오게 하려면 `xcom_pull`을 사용
    
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
    
5. NFT 정보 저장
    
    `BashOperator` 를 이용해서 bash 커맨드를 통해 추출한 csv 데이터를 sqlite db에 저장한다
    
    ```python
    storing_user = BashOperator(
        task_id='storing_user',
        bash_command='echo -e ".separator ","\n.import /tmp/processed_user.csv users" | sqlite3 /Users/yoohajun/Airflow/nft.db'
      )
    ```
    
    `echo -e ".separator ","\n.import /tmp/processed_user.csv users" | sqlite3 /Users/yoohajun/Airflow/nft.db`
    
    ⇒ csv 파일을 쪼개서 nfts 라는 테이블에 import 한다는 명령어
    

1. DAG 내 task 의존성 주입
    
    ```python
    ## DAG dependency insertion
    creating_table >> is_api_available >> extract_nft >> process_nft >> storing_user
    ```
    
    각 태스크에 `dag` 매개 변수를 전달하면 태스크가 동일한 DAG 인스턴스와 연결되어 `>>` 연산자를 사용하여 서로 관련될 수 있습니다.
    
    방법 1.
    
    ```python
    extract_nft = SimpleHttpOperator(
      task_id='extract_nft',
      http_conn_id='opensea_api',
      endpoint='api/v1/assets?collection=doodles-official&limit=1',
      method='GET',
      response_filter=lambda res: json.loads(res.text),
      log_response=True,
      dag=dag # 추가
    )
    ```
    
    방법 2
    
    ```python
    with DAG(dag_id='nft-pipeline',
             schedule_interval='@daily',
             default_args=default_args,
             tags=['nft'],
             catchup=False) as dag:
    ```
    
    ![스크린샷 2023-02-22 오후 5.20.31.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/ca9f43df-1f34-44e8-9d03-bf8e70bef182/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2023-02-22_%E1%84%8B%E1%85%A9%E1%84%92%E1%85%AE_5.20.31.png)
    

1. storing task revision
    
    위의 task는 저장을 할 때, token id가 중복되면 저장이 되지 않는다
    
    이미 저장된 row가 중복될 시 저장을 하지 않고 echo를 통해 탈출문을 출력하도록 한다.
    
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
    
2. Backfill 문제
    
    매일 주기적으로 돌아가는 파이프라인을 멈췄다가 몇 일 뒤에 실행시키면 어떻게 될까?
    
    DAG 스켈레톤 내에 catch up 파라미터를 통해 조절할 수 있다.
    
    start date부터 backfill을 실행할 것이다.
    
    마지막으로 돌리지 못했던 dag부터 backfill을 시도 ⇒ 밀렸던 몇 개의 DAG를 큐에 넣어 실행할 것이다.
