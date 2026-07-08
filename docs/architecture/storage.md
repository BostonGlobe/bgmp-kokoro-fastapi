# Storing Audio Files

## Problem
Once we have generated the audio for an article, we need a way to persist and expose the file so teams can integrate the audio into their product.
## Scale
- Audio file size:
	- Only used Globe articles
	- WAV: avg. 8.4 MB
	- MP3: avg. 3.2 MB
		- 2.5x compression from WAV
	- AAC: avg. 2.4 MB
		- 3.5x compression from WAV
- Avg. number of articles published per day: 
	- Globe: ~120
		- select COUNT(ARTICLE_ID) from NEWSROOM.ARC_STORY.VW_ARTICLES where PUBLISH_DATE >= DATEADD(day, -365, CURRENT_TIMESTAMP)
	- BDC: ~25
	- STAT: ?, error querying table
- Total data generated per day: 1.5 GB
	- 550 GB per year
		- in WAV format
	- 170 GB per year in MP3

## Approach
We are mounting NFS storage to the container to maintain the exisiting functionality of the POST /audio/speech and GET /download/{filename} endpoints. 