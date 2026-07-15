echo "Running siege stress test for GET /download/{filename}..."
export SIEGERC="siege.conf"
siege -C
siege -c 25 -t 15M --internet --content-type="application/json" -f urls/get-urls.txt
cat siege.log