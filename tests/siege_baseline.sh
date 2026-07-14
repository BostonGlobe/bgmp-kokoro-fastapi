# timestamp=$(date +"%Y%m%d-%H%M%S")
# log_file="results/siege_baseline-${timestamp}.log"
# mkdir -p results

echo "Word counts for test articles:"
wc -w data/*
echo ""

echo "Running siege baseline test for POST /audio/speech..."
export SIEGERC="siege.conf"
siege -C
siege -c 2 -r 5 -d 300.0 --internet --content-type="application/json" -f urls/baseline-urls.txt
