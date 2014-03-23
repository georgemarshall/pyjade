from __future__ import print_function
from optparse import OptionParser
from pyjade.utils import process
import codecs
import logging
import os


def convert_file():
    support_compilers_list = ['django', 'jinja', 'underscore', 'mako', 'tornado']
    available_compilers = {}
    for i in support_compilers_list:
        try:
            compiler_class = __import__('pyjade.ext.{0}'.format(i), fromlist=['pyjade']).Compiler
        except ImportError as e:
            logging.warning(e)
        else:
            available_compilers[i] = compiler_class

    usage = "usage: %prog [options] file [output]"
    parser = OptionParser(usage)
    parser.add_option("-o", "--output", dest="output",
                      help="Write output to FILE", metavar="FILE")
    # use a default compiler here to sidestep making a particular
    # compiler absolutely necessary (ex. django)
    default_compiler = sorted(available_compilers.keys())[0]
    parser.add_option("-c", "--compiler", dest="compiler",
                      choices=list(available_compilers.keys()),
                      default=default_compiler,
                      type="choice",
                      help=("COMPILER must be one of {0}, default is {1}"
                            .format(','.join(list(available_compilers.keys())), default_compiler)))
    parser.add_option("-e", "--ext", dest="extension",
                      help="Set import/extends default file extension",
                      metavar="FILE")

    options, args = parser.parse_args()
    if len(args) < 1:
        print("Specify the input file as the first argument.")
        exit()
    file_output = options.output or (args[1] if len(args) > 1 else None)
    compiler = options.compiler

    if options.extension:
        extension = '.{0}'.format(options.extension)
    elif options.output:
        extension = os.path.splitext(options.output)[1]
    else:
        extension = None

    if compiler in available_compilers:
        template = codecs.open(args[0], 'r', encoding='utf-8').read()
        output = process(template, compiler=available_compilers[compiler],
                         staticAttrs=True, extension=extension)
        if file_output:
            outfile = codecs.open(file_output, 'w', encoding='utf-8')
            outfile.write(output)
        else:
            print(output)
    else:
        raise Exception('You must have {0} installed!'.format(compiler))

if __name__ == '__main__':
    convert_file()
