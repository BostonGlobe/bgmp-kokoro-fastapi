echo "Running siege stress test for POST /audio/speech..."
export SIEGERC="siege.conf"
siege -C
siege -c 15 -r 1 --internet --content-type="application/json" -f urls/stress-urls.txt
