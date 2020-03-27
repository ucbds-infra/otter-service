from otter.grade import *
import pandas as pd
import subprocess
from subprocess import PIPE
import json
import re
from concurrent.futures import ThreadPoolExecutor, wait
import os
import shutil

def grade_assignment(tests_dir, notebook_path, id, image="ucbdsinfra/otter-grader", verbose=False, 
unfiltered_pdfs=False, tag_filter=False, html_filter=False, reqs=None, scripts=False, no_kill=False):
	"""
	Taken from https://github.com/ucbds-infra/otter-grader/blob/master/otter
	"""

	# launch our docker conainer
	launch_command = ["docker", "run", "-d","-it", image]
	launch = subprocess.run(launch_command, stdout=PIPE, stderr=PIPE)
	
	# print(launch.stderr)
	container_id = launch.stdout.decode('utf-8')[:-1]

	if verbose:
		print("Launched container {}...".format(container_id[:12]))
	
	# copy the notebook files to the container
	copy_command = ["docker", "cp", notebook_path, container_id+ ":/home/notebooks/"]
	copy = subprocess.run(copy_command, stdout=PIPE, stderr=PIPE)
	
	# copy the test files to the container
	tests_command = ["docker", "cp", tests_dir, container_id+ ":/home/tests/"]
	tests = subprocess.run(tests_command, stdout=PIPE, stderr=PIPE)

	# copy the requirements file to the container
	if reqs:
		if verbose:
			print("Installing requirements in container {}...".format(container_id[:12]))
		reqs_command = ["docker", "cp", reqs, container_id+ ":/home"]
		requirements = subprocess.run(reqs_command, stdout=PIPE, stderr=PIPE)

		# install requirements
		install_command = ["docker", "exec", "-t", container_id, "pip3", "install", "-r", "/home/requirements.txt"]
		install = subprocess.run(install_command, stdout=PIPE, stderr=PIPE)

	if verbose:
		print("Grading {} in container {}...".format(("notebooks", "scripts")[scripts], container_id[:12]))
	
	# Now we have the notebooks in home/notebooks, we should tell the container to execute the grade command....
	# grade_command = ["docker", "exec", "-t", container_id, "python3", "/home/grade.py", "/home/notebooks"]
	grade_command = ["docker", "exec", "-t", container_id, "python3", "-m", "otter.grade", "/home/notebooks"]

	# # if we want PDF output, add the necessary flag
	# if unfiltered_pdfs:
	#     grade_command += ["--pdf"]
	# if tag_filter:
	#     grade_command += ["--tag-filter"]
	# if html_filter:
	#     grade_command += ["--html-filter"]

	# if we are grading scripts, add the --script flag
	if scripts:
		grade_command += ["--scripts"]

	grade = subprocess.run(grade_command, stdout=PIPE, stderr=PIPE)
	
	# Logging stdout/stderr with print statements
	print(grade.stdout.decode('utf-8'))
	print(grade.stderr.decode('utf-8'))

	# Logging stdout/stderr to file
	log_file = open("log_file_container_ {}.txt".format(id), "a+")
	log_file.write(grade.stdout.decode('utf-8'))
	log_file.write("\n")
	log_file.write(grade.stderr.decode('utf-8'))
	log_file.write("\n")
	log_file.close()

	all_commands = [launch, copy, tests, grade]
	try:
		all_commands += [requirements, install]
	except UnboundLocalError:
		pass

	try:
		for command in all_commands:
			if command.stderr.decode('utf-8') != '':
				raise Exception("Error running ", command, " failed with error: ", command.stderr.decode('utf-8'))

		if verbose:
			print("Copying grades from container {}...".format(container_id[:12]))

		# get the grades back from the container and read to date frame so we can merge later
		csv_command = ["docker", "cp", container_id+ ":/home/notebooks/grades.csv", "./grades"+id+".csv"]
		csv = subprocess.run(csv_command, stdout=PIPE, stderr=PIPE)
		df = pd.read_csv("./grades"+id+".csv")


		if unfiltered_pdfs or tag_filter or html_filter:
			mkdir_pdf_command = ["mkdir", "manual_submissions"]
			mkdir_pdf = subprocess.run(mkdir_pdf_command, stdout=PIPE, stderr=PIPE)
			
			# copy out manual submissions
			for pdf in df["manual"]:
				copy_cmd = ["docker", "cp", container_id + ":" + pdf, "./manual_submissions/" + re.search(r"\/([\w\-\_]*?\.pdf)", pdf)[1]]
				copy = subprocess.run(copy_cmd, stdout=PIPE, stderr=PIPE)

			def clean_pdf_filepaths(row):
				path = row["manual"]
				return re.sub(r"\/home\/notebooks", "manual_submissions", path)

			df["manual"] = df.apply(clean_pdf_filepaths, axis=1)

		if not no_kill:
			if verbose:
				print("Stopping container {}...".format(container_id[:12]))

			# cleanup the docker container
			stop_command = ["docker", "stop", container_id]
			stop = subprocess.run(stop_command, stdout=PIPE, stderr=PIPE)
			remove_command = ["docker", "rm", container_id]
			remove = subprocess.run(remove_command, stdout=PIPE, stderr=PIPE)

	except BaseException as e:
		if not no_kill:
			if verbose:
				print("Stopping container {}...".format(container_id[:12]))

			# cleanup the docker container
			stop_command = ["docker", "stop", container_id]
			stop = subprocess.run(stop_command, stdout=PIPE, stderr=PIPE)
			remove_command = ["docker", "rm", container_id]
			remove = subprocess.run(remove_command, stdout=PIPE, stderr=PIPE)
		
		raise e
	
	# check that no commands errored, if they did raise an informative exception
	all_commands = [launch, copy, tests, grade, csv, stop, remove]
	try:
		all_commands += [requirements, install]
	except UnboundLocalError:
		pass
	for command in all_commands:
		if command.stderr.decode('utf-8') != '':
			raise Exception("Error running ", command, " failed with error: ", command.stderr.decode('utf-8'))
  
	return df