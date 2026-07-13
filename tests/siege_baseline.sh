timestamp=$(date +"%Y%m%d-%H%M%S")
log_file="results/siege_baseline-${timestamp}.log"

echo "Word counts for test articles:" >> "$log_file" 2>&1
wc -w data/* >> "$log_file" 2>&1
echo "" >> "$log_file" 2>&1

mkdir -p results
siege -c 1 -r once -v --internet --content-type="application/json" -f urls/post-urls.txt >> "$log_file" 2>&1

echo "" >> "$log_file" 2>&1

siege -c 1 -r once -v --internet -f urls/get-urls.txt >> "$log_file" 2>&1
