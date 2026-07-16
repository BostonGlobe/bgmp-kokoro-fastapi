echo "Running siege stress test for GET /download/{filename}..."
export SIEGERC="siege.conf"
siege -C
siege -c 100 -r 1 --internet --content-type="application/json" -f urls/stress-get-urls.txt