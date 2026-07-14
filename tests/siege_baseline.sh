timestamp=$(date +"%Y%m%d-%H%M%S")
log_file="results/siege_baseline-${timestamp}.log"
mkdir -p results

echo "Word counts for test articles:" >> "$log_file" 2>&1
wc -w data/* >> "$log_file" 2>&1
echo "" >> "$log_file" 2>&1

echo "Running siege baseline test for POST /audio/speech..." >> "$log_file" 2>&1
siege -c 2 -r 5 -d 300.0 --internet --content-type="application/json" -f urls/baseline-urls.txt >> "$log_file" 2>&1
