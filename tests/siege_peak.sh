# timestamp=$(date +"%Y%m%d-%H%M%S")
# log_file="results/siege_baseline-${timestamp}.log"
# mkdir -p results

echo "Word counts for test articles:"
wc -w data/*
echo ""

echo "Running siege peak test for POST /audio/speech..."
export SIEGERC="siege.conf"
siege -C
siege -c 5 -r 8 --internet --content-type="application/json" -f urls/post-urls.txt
cat siege.log