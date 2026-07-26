FROM apache/airflow:3.0.3

USER root
COPY scripts/ /opt/airflow/scripts/
RUN chmod +x /opt/airflow/scripts/bootstrap.sh
USER airflow

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
