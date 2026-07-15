echo "Running siege baseline test for GET /download/{filename}..."
export SIEGERC="siege.conf"
siege -C
siege -c 2 -r 5 -d 300.0 --internet --content-type="application/json" -f ../urls/get-urls.txt
cat siege.log