FROM rclone/rclone:1.69

COPY requirements_apk.txt /opt/requirements_apk.txt
COPY requirements.txt /opt/requirements.txt

RUN apk add --virtual=build_dependencies && \
    cat /opt/requirements_apk.txt | xargs apk add && \
    python3 -m venv /opt/datamount_venv && \
    /opt/datamount_venv/bin/pip install -r /opt/requirements.txt && \
    apk del --purge -r build_dependencies

RUN mkdir /mnt/data_mounts
COPY ./ /opt/datamount

#ENV FUSE_LIBRARY_PATH=/usr/lib/libfuse3.so.3
ENV FUSE_LIBRARY_PATH=/usr/lib/libfuse.so.2

USER root
EXPOSE 8090
EXPOSE 53682
WORKDIR /opt/datamount/project
ENTRYPOINT ["/opt/datamount_venv/bin/gunicorn", "-c", "/opt/datamount/gunicorn_http.py", "main:app"]
