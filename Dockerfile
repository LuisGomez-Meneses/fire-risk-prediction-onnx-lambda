FROM public.ecr.aws/lambda/python:3.10

# Install minimal dependencies needed by onnx and numpy
RUN yum install -y \
    libgomp \
    && yum clean all

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t ${LAMBDA_TASK_ROOT}

COPY lambda_function.py ${LAMBDA_TASK_ROOT}

CMD ["lambda_function.lambda_handler"]
