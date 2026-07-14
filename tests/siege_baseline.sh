timestamp=$(date +"%Y%m%d-%H%M%S")
log_file="results/siege_baseline-${timestamp}.log"
mkdir -p results

echo "Word counts for test articles:" >> "$log_file" 2>&1
wc -w data/* >> "$log_file" 2>&1
echo "" >> "$log_file" 2>&1

echo "Seeding data for siege baseline test..." >> "$log_file" 2>&1
siege -c 5 -r once -v --content-type="application/json" -f urls/seed-urls.txt >> "$log_file" 2>&1

echo "" >> "$log_file" 2>&1

siege -c 5 -t 15M -v -f urls/mixed-urls.txt >> "$log_file" 2>&1
