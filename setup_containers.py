from subprocess import PIPE
import subprocess
import shutil
import os
import yaml

def main():
    repo_path = input("What is the absolute path of your assignments repo? [/home/assignments] ")
    if not repo_path:
        repo_path = "/home/assignments"

    assert os.path.exists(repo_path) and os.path.isdir(repo_path), "{} does not exist or is not a directory".format(repo_path)

    os.chdir(repo_path)

    # get commit hash
    commit_hash_cmd = subprocess.run(["git", "rev-parse", "HEAD"], stdout=PIPE, stderr=PIPE)
    assert commit_hash_cmd, commit_hash_cmd.decode("utf-8")

    # get last known commit hash
    with open("/home/.LAST_COMMIT_HASH", "r+") as f:
        last_commit_hash = f.read()

    if last_commit_hash != commit_hash_cmd.stdout:
        # write commit hash
        with open("/home/.LAST_COMMIT_HASH", "w+") as f:
            f.write(commit_hash_cmd.stdout)
        
        print("No changes since last pull.")
        return
    
    # parse conf.yml
    assert os.path.isfile("conf.yml"), "conf.yml does not exist"
    with open("conf.yml") as f:
        config = yaml.safe_load(f)

    assignments = config["assignments"]
    ids = [a["assignment_id"] for a in assignments]
    assert len(ids) == len(set(ids)), "Found non-unique assignment IDs in conf.yml"

if __name__ == "__main__":
    main()
