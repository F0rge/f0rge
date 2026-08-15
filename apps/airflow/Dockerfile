# Shared f0rge Airflow 3 control plane (CeleryExecutor + GitDagBundle).
# 3.1.7 required for apache-airflow-providers-common-ai 0.7 (common-compat >=1.15).
FROM apache/airflow:3.1.7

USER root
COPY scripts/ /opt/airflow/scripts/
RUN chmod +x /opt/airflow/scripts/*.sh || true

USER airflow
COPY requirements.txt /requirements.txt
# Install as airflow user — 3.1.x image refuses pip as root.
RUN pip install --no-cache-dir \
      "apache-airflow==${AIRFLOW_VERSION}" \
      -r /requirements.txt
