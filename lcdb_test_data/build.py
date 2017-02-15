#!/usr/bin/env python

import subprocess as sp
import hashlib
import shlex
import pkg_resources
import os
import argparse
import shutil

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

usage = """
Builds a set of example data (FASTA, FASTQ, BAM, GTF) in the specified
directory.

Automatically creates a conda environment in that directory to run the
snakefile.

Extra arguments are sent to Snakemake (e.g., -npr or -j8).
"""

def main():
    ap = argparse.ArgumentParser(usage=usage)
    ap.add_argument('data_dir', help='Location in which to build data set')
    args, extra = ap.parse_known_args()

    b = Builder(args.data_dir)
    b.build_environment()
    b.write_snakefile()
    b.run_snakefile(extra)


class Builder(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.env_path = None
        if not os.path.exists(self.data_dir):
            logger.info('Creating %s', self.data_dir)
            os.makedirs(self.data_dir)

    def build_environment(self):
        """
        Creates the environment in a subdirectory named after the md5sum of the
        included environment.yml. If the path already exists then skip
        building.

        If successful the environment path is stored in self.env_path for later
        use.
        """
        md5hash = hashlib.md5()
        contents = pkg_resources.resource_string('lcdb_test_data', 'requirements.txt')
        md5hash.update(contents)
        with open(os.path.join(self.data_dir, 'requirements.txt'), 'wb') as fout:
            fout.write(contents)

        # The command will be run with cwd set to self.data_dir, but it will be
        # useful to report the full path, so create both
        env_path = os.path.join(self.data_dir, '.conda-env', md5hash.hexdigest()[:6])
        rel_env = os.path.relpath(env_path, self.data_dir)
        if not os.path.exists(os.path.join(env_path, '.success')):
            logger.info("Building environment in %s", os.path.abspath(env_path))
            os.makedirs(env_path)
            cmd = ['conda', 'create', '-y', '--file', 'requirements.txt',
                   '--prefix', rel_env, 'python=3']
            p = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, bufsize=-1,
                         cwd=self.data_dir)
            for i in p.stdout:
                print(i[:-1].decode())
            retcode = p.wait()
            if retcode:
                logger.error("CMDS: %s", cmd)
                raise sp.CalledProcessError(retcode, cmd)
            logger.info('Built environment %s', env_path)

            with open(os.path.join(env_path, '.success'), 'w') as fout:
                pass

        else:
            logger.info('Using existing environment %s', os.path.abspath(env_path))
        self.env_path = env_path

    def write_snakefile(self):
        """
        Write the Snakefile to the data dir
        """
        with open(os.path.join(self.data_dir, 'Snakefile'), 'wb') as fout:
            fout.write(pkg_resources.resource_string('lcdb_test_data', 'Snakefile'))
        return fout.name

    def run_snakefile(self, additional_args=""):
        """
        Activate the built environment and run snakemake in the data dir.

        `additional_args` is a string of args to pass verbatim to snakemake,
        e.g., "-j4 -T", or "-n".
        """
        logger.info('Running snakemake in %s', self.data_dir)
        additional_args = ' '.join(additional_args)
        cmd = "source activate {}; snakemake {}".format(
            os.path.relpath(
                self.env_path, self.data_dir
            ), additional_args)

        p = sp.Popen(
            cmd,
            cwd=self.data_dir,
            shell=True,
            stdout=sp.PIPE,
            stderr=sp.STDOUT,
            bufsize=-1,
            executable='/bin/bash',
        )
        for i in p.stdout:
            print(i[:-1].decode())
        retcode = p.wait()
        if retcode:
            logger.error("CMDS: %s", cmd)
            raise sp.CalledProcessError(retcode, cmd)
