for p in projects/*; do
    pushd $p;
    poetry build-project;
    popd;
done
