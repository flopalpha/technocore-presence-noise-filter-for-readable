'''Command line for readable review.'''

import argparse
from pathlib import Path

import presence_filter as pf

def build_parser():
    p = argparse.ArgumentParser(description='Filter presence noise and surface substantive posts.')
    p.add_argument('input', help='Input log file with json lines or pipe lines.')
    p.add_argument('-o', '--output', default='review.md', help='Output markdown file.')
    p.add_argument('--min-cluster', type=int, default=2, help='Smallest group to keep.')
    return p

def main():
    parser = build_parser()
    args = parser.parse_args()
    posts = pf.parse_log_file(args.input)
    classified = pf.classify_all(posts)
    clusters = pf.cluster_posts(posts)
    keep = []
    for c in clusters:
        if c.get('count', 0) >= args.min_cluster:
            keep.append(c)
    substantive = pf.surface_substantive(classified)
    summary = pf.summarize(classified, clusters)
    out_path = str(Path(args.output))
    pf.write_markdown_summary(summary, substantive, keep, out_path)
    print('Total: ' + str(summary['total']))
    print('Noise: ' + str(summary['noise']))
    print('Signal: ' + str(summary['signal']))
    print('Wrote: ' + out_path)
    for item in substantive[:10]:
        print('seq ' + str(item.get('seq')) + ' ' + str(item.get('category')))

if __name__ == '__main__':
    main()
