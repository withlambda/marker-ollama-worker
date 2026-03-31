FROM notelm-mineru-review

RUN python -m pip install \
    'shapely>=2.0.7,<3.0.0' \
    'pyclipper<2,>=1.3.0' \
    'omegaconf<3,>=2.3.0' \
    'ftfy<7,>=6.3.1'
