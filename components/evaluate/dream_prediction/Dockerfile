FROM python:3.5.6

LABEL Khaos Research Group <khaos.uma.es>

LABEL Adrián Segura Ortiz <adrianseor.99@gmail.com>

RUN apt-get update && apt-get install -y \
   curl \
   libssl-dev \
   libcurl4-openssl-dev \
   libxml2-dev

# Update pip command
RUN pip install --upgrade pip

# Install required cpython
RUN pip install cython 

# Install packages
RUN pip install dreamtools argparse pandas


COPY components /usr/local/src/components
WORKDIR /usr/local/src/

ENTRYPOINT ["python", "components/evaluate/dream_prediction/evaluation.py"]
