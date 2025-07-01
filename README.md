# BucketHead

**BucketHead** is a Python tool for detecting and exfiltrating from **publicly accessible AWS S3 buckets**.  
It takes either:
- an exact bucket name, or  
- a list of keywords to generate and brute-check likely bucket name permutations.

If a bucket is public, it downloads any listed files and scans `.txt` files for secrets like:
- passwords
- API keys
- tokens
- database strings

---

## ⚙ Requirements

- Python 3.7+
- `requests` library

Install this if you haven't:
```bash
pip install requests
