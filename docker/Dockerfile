# Copyright 2024 DeepMind Technologies Limited
#
# AlphaFold 3 source code is licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# To request access to the AlphaFold 3 model parameters, follow the process set
# out at https://github.com/google-deepmind/alphafold3. You may only use these
# if received directly from Google. Use is subject to terms of use available at
# https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md

FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/nvidia/cuda:12.6.3-base-ubuntu24.04

# Switch apt sources to Aliyun mirror for faster downloads in China.
RUN sed -i 's|http://archive.ubuntu.com|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/ubuntu.sources \
    && sed -i 's|http://security.ubuntu.com|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/ubuntu.sources

# Some RUN statements are combined together to make Docker build run faster.
# Get latest package listing, install python, git, wget, compilers and libs.
# * git is required for pyproject.toml toolchain's use of CMakeLists.txt.
# * gcc, g++, make are required for compiling HMMER and AlphaFold 3 libaries.
# * zlib is a required dependency of AlphaFold 3.
RUN DEBIAN_FRONTEND=noninteractive \
apt-get update --quiet \
&& apt-get install --yes --quiet python3.12 python3.12-dev python3-pip \
&& apt-get install --yes --quiet git wget gcc g++ make zlib1g-dev zstd

# Install uv via pip using Tsinghua PyPI mirror.
RUN pip3 install --no-cache-dir --break-system-packages uv==0.9.24 -i https://pypi.tuna.tsinghua.edu.cn/simple

# UV_COMPILE_BYTECODE=1 speeds up future container starts.
# UV_PROJECT_ENVIRONMENT explicitly sets the virtual environment location.
ENV UV_COMPILE_BYTECODE=1
ENV UV_PROJECT_ENVIRONMENT=/alphafold3_venv
RUN uv venv $UV_PROJECT_ENVIRONMENT

ENV PATH="/hmmer/bin:/alphafold3_venv/bin:$PATH"

# Install HMMER. Do so before copying the source code, so that docker can cache
# the image layer containing HMMER. Alternatively, you could also install it
# using `apt-get install hmmer` instead of bulding it from source, but we want
# to have control over the exact version of HMMER and also apply the sequence
# limit patch. Also note that eddylab.org unfortunately doesn't support HTTPS
# and the tar file published on GitHub is explicitly not recommended to be used
# for building from source.

# Copy, check hash, and extract the HMMER source code.
RUN mkdir /hmmer_build /hmmer
COPY docker/hmmer-3.4.tar.gz /hmmer_build/
RUN (cd /hmmer_build && echo "ca70d94fd0cf271bd7063423aabb116d42de533117343a9b27a65c17ff06fbf3 hmmer-3.4.tar.gz" | sha256sum --check) && \
    (cd /hmmer_build && tar zxf hmmer-3.4.tar.gz && rm hmmer-3.4.tar.gz)

# Apply the --seq_limit patch to HMMER.
COPY docker/jackhmmer_seq_limit.patch /hmmer_build/
RUN (cd /hmmer_build && patch -p0 < jackhmmer_seq_limit.patch)

# Build HMMER.
RUN (cd /hmmer_build/hmmer-3.4 && ./configure --prefix /hmmer) && \
    (cd /hmmer_build/hmmer-3.4 && make -j) && \
    (cd /hmmer_build/hmmer-3.4 && make install) && \
    (cd /hmmer_build/hmmer-3.4/easel && make install) && \
    rm -R /hmmer_build

# Copy the AlphaFold 3 source code from the local machine to the container and
# set the working directory to there.
COPY . /app/alphafold
WORKDIR /app/alphafold

# Install the exact dependency tree using uv and cache the build artifacts.
# --frozen: do not update the lockfile during build.
# --all-groups: install development/test dependencies defined in pyproject.toml.
# --no-editable: install as a static package.
# If using this as a recipe for local installation, we recommend removing the
# --frozen and --no-editable flags.
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_LINK_MODE=copy uv sync --all-groups --no-editable \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Build chemical components database (this binary was installed by uv sync).
RUN uv run build_data

# To work around a known XLA issue causing the compilation time to greatly
# increase, the following environment variable setting XLA flags must be enabled
# when running AlphaFold 3. Note that if using CUDA capability 7 GPUs, it is
# necessary to set the following XLA_FLAGS value instead:
# ENV XLA_FLAGS="--xla_disable_hlo_passes=custom-kernel-fusion-rewriter"
# (no need to disable gemm in that case as it is not supported for such GPU).
ENV XLA_FLAGS="--xla_gpu_enable_triton_gemm=false"
# Memory settings used for folding up to 5,120 tokens on A100 80 GB.
ENV XLA_PYTHON_CLIENT_PREALLOCATE=true
ENV XLA_CLIENT_MEM_FRACTION=0.95

CMD ["uv", "run", "python3", "run_alphafold.py"]
