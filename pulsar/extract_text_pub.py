import argparse
import sys
import logging
import pulsar
import boto3
import json

__author__ = "Phat Loc"
__copyright__ = "Phat Loc"
__license__ = "mit"

_logger = logging.getLogger(__name__)

DEFAULT_FORM_TYPES = ['8-K',
                      '8-K/A',
                      'SC 13D',
                      'SC 13D/A',
                      'SC 13E3',
                      'SC 13E3/A',
                      '10-Q',
                      '10-Q/A',
                      '10-K',
                      '10-K/A',
                      'DEF 14A',
                      'DEF 14C',
                      'DEFA14C',
                      'DEFC14A',
                      'DEFC14C',
                      'DEFM14A',
                      'DEFM14C',
                      'DEFN14A',
                      'DEFR14A',
                      'DEFR14C',
                      'DEL AM',
                      'DFAN14A',
                      'DFRN14A',
                      'SC 14D9',
                      'SC 14D9/A',
                      'SC 14F1',
                      'SC 14F1/A',
                      'SC TO-C',
                      'SC TO-I',
                      'SC TO-I/A',
                      'SC TO-T',
                      'SC TO-T/A',
                      'SC13E4F',
                      'SC13E4F/A',
                      'SC14D1F',
                      'SC14D1F/A',
                      'SC14D9C',
                      '424A',
                      '424B1',
                      '424B2',
                      '424B3',
                      '424B4',
                      '424B5',
                      '424B7',
                      '424B8',
                      '425',
                      'CB',
                      'CB/A']


def fetch_s3_keys(cik: str = "315852", form_type: str = "8-K", date_str: str = "20191024",
                  bucket: str = "dataengine-xyz-edgar-raw-data"):
    """

    :param cik:
    :param form_type:
    :param date_str:
    :param bucket:
    :return:
    """
    assert cik is not None
    assert (form_type is None and date_str is None) or (form_type is not None)
    prefix_parts = [p for p in [cik, form_type, date_str] if p is not None]
    if len(prefix_parts) > 1:
        prefix = "|".join(prefix_parts)
    else:
        prefix = cik + "|"

    client = boto3.client('s3')
    paginator = client.get_paginator('list_objects')
    operation_parameters = {'Bucket': bucket,
                            'Prefix': prefix}
    page_iterator = paginator.paginate(**operation_parameters)
    s3_keys = []

    for page in page_iterator:
        s3_keys.extend(map(lambda s3_file: {"bucket": bucket, "key": s3_file.get('Key')}, page['Contents']))

    return s3_keys


def s3_files_to_extract_text_publish(s3_keys: iter,
                                     pulsar_topic: str = "extract_text",
                                     pulsar_connection_string: str = "pulsar://localhost:6650"):
    """

    :param s3_keys:
    :param pulsar_topic:
    :param pulsar_connection_string:
    :return:
    """
    client = pulsar.Client(pulsar_connection_string)
    try:
        producer = client.create_producer(topic=pulsar_topic,
                                          message_routing_mode=pulsar.PartitionsRoutingMode.RoundRobinDistribution)
        i = 1
        total = len(s3_keys)
        for payload in s3_keys:
            msg = json.dumps(payload).encode('utf-8')
            producer.send(msg)
            _logger.info("Published {i} of {total} messages to {topic}".format(i=i, total=total, topic=pulsar_topic))
    finally:
        client.close()


def extract_text_by_form_types(cik: str, form_types: str, date_str: str, bucket: str, pulsar_topic: str,
                               pulsar_connection_string: str):
    """

    :param cik:
    :param form_types:
    :param date_str:
    :param bucket:
    :param pulsar_topic:
    :param pulsar_connection_string:
    :return:
    """
    for form_type in form_types.split(','):
        s3_keys = fetch_s3_keys(cik=cik, form_type=form_type, date_str=date_str, bucket=bucket)
        s3_files_to_extract_text_publish(s3_keys=s3_keys,
                                         pulsar_topic=pulsar_topic,
                                         pulsar_connection_string=pulsar_connection_string)


def parse_args(args):
    """Parse command line parameters

    Args:
      args ([str]): command line parameters as list of strings

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(
        description="")
    parser.add_argument(dest="cik",
                        help="CIK number of the company to extract text from",
                        type=str)

    parser.add_argument("-fts",
                        "--form_types",
                        help="Comma separated value of form types see https://en.wikipedia.org/wiki/SEC_filing",
                        type=str,
                        default=','.join(DEFAULT_FORM_TYPES))

    parser.add_argument("-fd",
                        "--filing_date",
                        help="The filing date to pull filings from YYYYMMDD format",
                        type=str)

    parser.add_argument("-pt",
                        "--pulsar_topic",
                        help="Pulsar topic to publish to",
                        type=str,
                        default='extract_text')

    parser.add_argument("-pcs",
                        "--pulsar_connection_string",
                        help="Pulsar connection string e.g. pulsar://localhost:6650",
                        type=str,
                        default="pulsar://ip-10-0-0-11.ec2.internal:6650,pulsar://ip-10-0-0-12.ec2.internal:6650,pulsar://ip-10-0-0-13.ec2.internal:6650")

    parser.add_argument("-bkt",
                        "--bucket",
                        help="S3 Bucket to pull from",
                        type=str,
                        default='dataengine-xyz-edgar-raw-data')

    parser.add_argument(
        "-v",
        "--verbose",
        dest="loglevel",
        help="set loglevel to INFO",
        action="store_const",
        const=logging.INFO)
    parser.add_argument(
        "-vv",
        "--very-verbose",
        dest="loglevel",
        help="set loglevel to DEBUG",
        action="store_const",
        const=logging.DEBUG)
    return parser.parse_args(args)


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=loglevel, stream=sys.stdout,
                        format=logformat, datefmt="%Y-%m-%d %H:%M:%S")


def main(args):
    """Main entry point allowing external calls

    Args:
      args ([str]): command line parameter list
    """
    args = parse_args(args)
    setup_logging(args.loglevel)
    extract_text_by_form_types(cik=args.cik, form_types=args.form_types, date_str=args.filing_date, bucket=args.bucket,
                               pulsar_topic=args.pulsar_topic, pulsar_connection_string=args.pulsar_connection_string)


def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
