import os
import re
import six


class Compiler(object):
    RE_INTERPOLATE = re.compile(r'(\\)?([#!]){(.*?)}')
    doctypes = {
        'default': '<!DOCTYPE html>',
        'xml': '<?xml version="1.0" encoding="utf-8" ?>',
        'transitional': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">',
        'strict': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">',
        'frameset': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Frameset//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd">',
        '1.1': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">',
        'basic': '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML Basic 1.1//EN" "http://www.w3.org/TR/xhtml-basic/xhtml-basic11.dtd">',
        'mobile': '<!DOCTYPE html PUBLIC "-//WAPFORUM//DTD XHTML Mobile 1.2//EN" "http://www.openmobilealliance.org/tech/DTD/xhtml-mobile12.dtd">'
    }
    inlineTags = [
        'a',
        'abbr',
        'acronym',
        'b',
        'br',
        'code',
        'em',
        'font',
        'i',
        'img',
        'ins',
        'kbd',
        'map',
        'samp',
        'small',
        'span',
        'strong',
        'sub',
        'sup'
    ]
    selfClosing = [
        'area',
        'base',
        'br',
        'col',
        'embed',
        'hr',
        'img',
        'input',
        'keygen',
        'link',
        'menuitem',
        'meta',
        'param',
        'source',
        'track',
        'wbr'
    ]
    autocloseCode = ['if', 'for', 'block', 'filter', 'autoescape', 'with', 'trans', 'spaceless', 'comment', 'cache', 'macro', 'localize', 'compress']

    filters = {}

    def __init__(self, node, **options):
        self.options = options
        self.node = node
        self.hasCompiledDoctype = False
        self.hasCompiledTag = False
        self.pp = options.get('pretty', True)
        self.debug = options.get('compileDebug', False) is not False
        self.filters.update(options.get('filters', {}))
        self.doctypes.update(options.get('doctypes', {}))
        # self.var_processor = options.get('var_processor', lambda x: x)
        self.selfClosing.extend(options.get('selfClosing', []))
        self.autocloseCode.extend(options.get('autocloseCode', []))
        self.inlineTags.extend(options.get('inlineTags', []))
        self.useRuntime = options.get('useRuntime', True)
        self.extension = options.get('extension', None) or '.jade'
        self.indents = 0
        self.doctype = None
        self.terse = False
        self.xml = False
        self.mixing = 0
        self.variable_start_string = options.get("variable_start_string", "{{")
        self.variable_end_string = options.get("variable_end_string", "}}")
        if 'doctype' in self.options:
            self.setDoctype(options['doctype'])
        self.instring = False

    def var_processor(self, var):
        if isinstance(var, six.string_types) and var.startswith('_ '):
            var = '_("{0}")'.format(var[2:])
        return var

    def compile_top(self):
        return ''

    def compile(self):
        self.buf = [self.compile_top()]
        self.lastBufferedIdx = -1
        self.visit(self.node)
        compiled = u''.join(self.buf)
        if isinstance(compiled, six.binary_type):
            compiled = six.text_type(compiled, 'utf8')
        return compiled

    def setDoctype(self, name):
        self.doctype = self.doctypes.get(name or 'default',
                                         '<!DOCTYPE {0}>'.format(name))
        self.terse = name in ('5', 'html')
        self.xml = self.doctype.startswith('<?xml')

    def buffer(self, str):
        if self.lastBufferedIdx == len(self.buf):
            self.lastBuffered += str
            self.buf[self.lastBufferedIdx - 1] = self.lastBuffered
        else:
            self.buf.append(str)
            self.lastBuffered = str
            self.lastBufferedIdx = len(self.buf)

    def visit(self, node, *args, **kwargs):
        # debug = self.debug
        # if debug:
        #     self.buf.append('__jade.unshift({ lineno: %d, filename: %s });' % (node.line,('"%s"'%node.filename) if node.filename else '__jade[0].filename'));

        # if node.debug==False and self.debug:
        #     self.buf.pop()
        #     self.buf.pop()

        self.visitNode(node, *args, **kwargs)
        # if debug: self.buf.append('__jade.shift();')

    def visitNode(self, node, *args, **kwargs):
        name = node.__class__.__name__
        if self.instring and name != 'Tag':
            self.buffer('\n')
            self.instring = False
        return getattr(self, 'visit{0}'.format(name))(node, *args, **kwargs)

    def visitLiteral(self, node):
        self.buffer(node.str)

    def visitBlock(self, block):
        for node in block.nodes:
            self.visit(node)

    def visitCodeBlock(self, block):
        self.buffer('{%% block %s %%}' % block.name)
        if block.mode == 'prepend':
            self.buffer('{0}super(){1}'.format(self.variable_start_string,
                                               self.variable_end_string))
        self.visitBlock(block)
        if block.mode == 'append':
            self.buffer('{0}super(){1}'.format(self.variable_start_string,
                                               self.variable_end_string))
        self.buffer('{% endblock %}')

    def visitDoctype(self, doctype=None):
        if doctype and (doctype.val or not self.doctype):
            self.setDoctype(doctype.val or 'default')

        if self.doctype:
            self.buffer(self.doctype)
        self.hasCompiledDoctype = True

    def visitMixin(self, mixin):
        if mixin.block:
            self.buffer('{%% macro %s(%s) %%}' % (mixin.name, mixin.args))
            self.visitBlock(mixin.block)
            self.buffer('{% endmacro %}')
        else:
            self.buffer('{0]{1.name}({1.args}){2}'.format(self.variable_start_string, mixin,
                                                          self.variable_end_string))

    def visitTag(self, tag):
        self.indents += 1
        name = tag.name
        if not self.hasCompiledTag:
            if not self.hasCompiledDoctype and 'html' == name:
                self.visitDoctype()
            self.hasCompiledTag = True

        if self.pp and name not in self.inlineTags and not tag.inline:
            self.buffer('\n' + '  ' * (self.indents - 1))
        if name in self.inlineTags or tag.inline:
            self.instring = False

        closed = name in self.selfClosing and not self.xml
        self.buffer('<%s' % name)
        self.visitAttributes(tag.attrs)
        self.buffer('/>' if not self.terse and closed else '>')

        if not closed:
            if tag.code:
                self.visitCode(tag.code)
            if tag.text:
                self.buffer(self.interpolate(tag.text.nodes[0].lstrip()))
            self.escape = 'pre' == tag.name
            # empirically check if we only contain text
            textOnly = tag.textOnly or not bool(len(tag.block.nodes))
            self.instring = False
            self.visit(tag.block)

            if self.pp and not name in self.inlineTags and not textOnly:
                self.buffer('\n' + '  ' * (self.indents-1))

            self.buffer('</%s>' % name)
        self.indents -= 1

    def visitFilter(self, filter):
        if filter.name not in self.filters:
            if filter.isASTFilter:
                raise Exception('unknown ast filter "{0}"'.format(filter.name))
            else:
                raise Exception('unknown filter "{0}"'.format(filter.name))

        fn = self.filters.get(filter.name)
        if filter.isASTFilter:
            self.buf.append(fn(filter.block, self, filter.attrs))
        else:
            text = ''.join(filter.block.nodes)
            text = self.interpolate(text)
            filter.attrs = filter.attrs or {}
            filter.attrs['filename'] = self.options.get('filename', None)
            self.buffer(fn(text, filter.attrs))

    def _interpolate(self, attr, repl):
        return self.RE_INTERPOLATE.sub(lambda matchobj: repl(matchobj.group(3)),
                                       attr)

    def interpolate(self, text, escape=True):
        if escape:
            return self._interpolate(text, lambda x: '{0}{1}|escape{2}'.format(self.variable_start_string, x, self.variable_end_string))
        return self._interpolate(text, lambda x: '{0}{1}{2}'.format(self.variable_start_string, x, self.variable_end_string))

    def visitText(self, text):
        script = text.parent and text.parent.name == 'script'
        text = ''.join(text.nodes)
        text = self.interpolate(text, script)
        self.buffer(text)
        if self.pp:
            self.buffer('\n')

    def visitString(self, text):
        text = ''.join(text.nodes)
        text = self.interpolate(text)
        self.buffer(text)
        self.instring = True

    def visitComment(self, comment):
        if not comment.buffer:
            return
        if self.pp:
            self.buffer('\n' + '  ' * (self.indents))
        self.buffer('<!--{0}-->'.format(comment.val))

    def visitAssignment(self, assignment):
        self.buffer('{%% set %s = %s %%}' % (assignment.name, assignment.val))

    def format_path(self, path):
        has_extension = os.path.basename(path).find('.') > -1
        if not has_extension:
            path += self.extension
        return path

    def visitExtends(self, node):
        path = self.format_path(node.path)
        self.buffer('{%% extends "%s" %%}' % (path))

    def visitInclude(self, node):
        path = self.format_path(node.path)
        self.buffer('{%% include "%s" %%}' % (path))

    def visitBlockComment(self, comment):
        if not comment.buffer:
            return
        isConditional = comment.val.strip().startswith('if')
        self.buffer('<!--[{0}]>'.format(comment.val.strip()) if isConditional else '<!--{0}'.format(comment.val))
        self.visit(comment.block)
        self.buffer('<![endif]-->' if isConditional else '-->')

    def visitConditional(self, conditional):
        TYPE_CODE = {
            'if': lambda x: 'if {0}'.format(x),
            'unless': lambda x: 'if not {0}'.format(x),
            'elif': lambda x: 'elif {0}'.format(x),
            'else': lambda x: 'else'
        }
        self.buf.append('{%% %s %%}' % TYPE_CODE[conditional.type](conditional.sentence))
        if conditional.block:
            self.visit(conditional.block)
            for next in conditional.next:
                self.visitConditional(next)
        if conditional.type in ('if', 'unless'):
            self.buf.append('{% endif %}')

    def visitVar(self, var, escape=False):
        var = self.var_processor(var)
        return ('{0}{1}{2}{3}'.format(self.variable_start_string, var,
                                      '|escape' if escape else '', self.variable_end_string))

    def visitCode(self, code):
        if code.buffer:
            val = code.val.lstrip()

            self.buf.append(self.visitVar(val, code.escape))
        else:
            self.buf.append('{%% %s %%}' % code.val)

        if code.block:
            # if not code.buffer: self.buf.append('{')
            self.visit(code.block)
            # if not code.buffer: self.buf.append('}')

            if not code.buffer:
                codeTag = code.val.strip().split(' ', 1)[0]
                if codeTag in self.autocloseCode:
                    self.buf.append('{%% end%s %%}' % codeTag)

    def visitEach(self, each):
        self.buf.append('{%% for %s in %s|__pyjade_iter:%d %%}' % (','.join(each.keys), each.obj, len(each.keys)))
        self.visit(each.block)
        self.buf.append('{% endfor %}')

    def attributes(self, attrs):
        return '{0}__pyjade_attrs({1}){2}'.format(self.variable_start_string, attrs, self.variable_end_string)

    def visitDynamicAttributes(self, attrs):
        buf, classes, params = [], [], {}
        terse = 'terse=True' if self.terse else ''
        for attr in attrs:
            if attr['name'] == 'class':
                classes.append('({0})'.format(attr['val']))
            else:
                pair = "('{0}',({1}))".format(attr['name'], attr['val'])
                buf.append(pair)

        if classes:
            classes = " , ".join(classes)
            buf.append("('class', ({0}))".format(classes))

        buf = ', '.join(buf)
        if self.terse:
            params['terse'] = 'True'
        if buf:
            params['attrs'] = '[{0}]'.format(buf)
        param_string = ', '.join(['{0}={1}'.format(n, v) for n, v in six.iteritems(params)])
        if buf or terse:
            self.buf.append(self.attributes(param_string))

    def visitAttributes(self, attrs):
        temp_attrs = []
        for attr in attrs:
            if (not self.useRuntime and not attr['name'] == 'class') or attr['static']:
                if temp_attrs:
                    self.visitDynamicAttributes(temp_attrs)
                    temp_attrs = []
                n, v = attr['name'], attr['val']
                if isinstance(v, six.string_types):
                    if self.useRuntime or attr['static']:
                        self.buf.append(' {0}={1}'.format(n, v))
                    else:
                        self.buf.append(' {0}="{1}"'.format(n, self.visitVar(v)))
                elif v is True:
                    if self.terse:
                        self.buf.append(' {0}'.format(n))
                    else:
                        self.buf.append(' {0}="{1}"'.format(n, n))
            else:
                temp_attrs.append(attr)

        if temp_attrs:
            self.visitDynamicAttributes(temp_attrs)

    @classmethod
    def register_filter(cls, name, f):
        cls.filters[name] = f

    @classmethod
    def register_autoclosecode(cls, name):
        cls.autocloseCode.append(name)
