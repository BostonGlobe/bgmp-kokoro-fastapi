echo "Running siege peak test for POST /audio/speech..."
export SIEGERC="siege.conf"
siege -C
siege -c 5 -r 8 --internet --content-type="application/json" -f urls/post-urls.txt