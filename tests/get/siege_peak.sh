echo "Running siege peak test for GET /download/{filename}..."
export SIEGERC="siege.conf"
siege -C
siege -c 5 -r 8 --internet --content-type="application/json" -f urls/get-urls.txt