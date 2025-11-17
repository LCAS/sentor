ARG BASE_IMAGE=lcas.lincoln.ac.uk/lcas/ros-docker-images:humble-2

FROM ${BASE_IMAGE} AS base

USER root

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -qq -y --no-install-recommends \
    git \
    python3-pip \
    python3-rosdep

# get the source tree and analyse it for its package.xml only
FROM base AS sourcefilter
COPY ./src /tmp/src
# remove everything that isn't package.xml
RUN find /tmp/src -type f \! -name "package.xml" -print | xargs rm -rf

# install all dependencies listed in the package.xml
FROM base AS depbuilder
# copy the reduced source tree (only package.xml) from previous stage
COPY --from=sourcefilter /tmp/src /tmp/src
RUN rosdep update --rosdistro ${ROS_DISTRO} && apt-get update
RUN cd /tmp/src && rosdep install --from-paths . --ignore-src -r -y && cd && rm -rf /tmp/src

FROM depbuilder AS final

RUN pip install black flake8

# add user ros if it doesn't exist yet, and add them to the sudo group
RUN id -u ros || adduser --disabled-password --uid 1000 --gecos "" ros \
    && usermod -aG sudo ros

# enable sudo without password for sudo group
RUN echo "%sudo ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER ros

