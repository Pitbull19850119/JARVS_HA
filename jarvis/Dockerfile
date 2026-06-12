ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip tzdata

COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt || \
    pip3 install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /usr/share/jarvis

COPY rootfs /
COPY jarvis_server.py /usr/bin/jarvis_server.py
COPY index.html /usr/share/jarvis/index.html

RUN chmod a+x /usr/bin/jarvis_server.py \
    && chmod a+x /etc/services.d/jarvis/run \
    && chmod a+x /etc/services.d/jarvis/finish
