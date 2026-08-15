# Shared f0rge Airflow 3 control plane (LocalExecutor).
# Stay on 3.0.3 until a deliberate upgrade; that is what already runs on rpi.
FROM apache/airflow:3.0.3

USER root
COPY scripts/ /opt/airflow/scripts/
RUN chmod +x /opt/airflow/scripts/*.sh || true
USER airflow
