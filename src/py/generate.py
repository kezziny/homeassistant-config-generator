from pathlib import Path;
import yaml;
import json;
import sys;

from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO

from ruamel.yaml.scalarstring import LiteralScalarString, preserve_literal, FoldedScalarString;

basepath = "."

def walk_tree(base):
    from ruamel.yaml.compat import string_types

    def test_wrap(v):
        if v.find("\n") > -1:
            return FoldedScalarString(v.replace('\r\n', '\n').replace('\r', '\n'));
        return v;

    if isinstance(base, dict):
        for k in base:
            v = base[k]
            if isinstance(v, string_types) and '\n' in v:
                base[k] = test_wrap(v)
            else:
                walk_tree(v)
    elif isinstance(base, list):
        for idx, elem in enumerate(base):
            if isinstance(elem, string_types) and '\n' in elem:
                base[idx] = test_wrap(elem)
            else:
                walk_tree(elem)

class MyYAML(YAML):
    def dump(self, data, stream=None, **kw):
        inefficient = False
        if stream is None:
            inefficient = True
            stream = StringIO()
        YAML.dump(self, data, stream, **kw)
        if inefficient:
            return stream.getvalue()

yaml2 = MyYAML();
yaml2.width = 4096

def my_compose_document(self):
    self.parser.get_event()
    node = self.compose_node(None, None)
    self.parser.get_event()
    # self.anchors = {}    # <<<< commented out
    return node

yaml2.Composer.compose_document = my_compose_document

# adapted from http://code.activestate.com/recipes/577613-yaml-include-support/
def yaml_include(loader, node):
    y = loader.loader
    yaml = YAML(typ=y.typ, pure=y.pure)  # same values as including YAML
    yaml.composer.anchors = loader.composer.anchors
    log.info("include: " + node.value + str(loader));
    f = open(basepath + "/" + node.value)
    log.info("opened");
    return yaml.load(f.read())

yaml2.Constructor.add_constructor("!include", yaml_include)


class Log:
    def __init__(self, path):
        self.file = open(path, 'w');
    
    def __del__(self):
        self.file.close();

    def info(self, message):
        self.file.write("[INFO ]: " + message + "\n");
    
    def error(self, message):
        self.file.write("[ERROR]: " + message + "\n");
    
class DummyLog:
    def __init__(self, path):
        pass
    
    def __del__(self):
        pass

    def info(self, message):
        pass
    
    def error(self, message):
        pass
        

log = Log('/config/config_generator.log');
writer = None;

log.info("start");

class BufferedWriter:
    def __init__(self, basepath):
        self.base = basepath;
        self.files = {};
    
    def flush(self):
        log.info("flushing" + str(len(self.files)));
        for path in self.files:
            log.info(self.base + "/" + path);
            with open(self.base + "/" + path, 'w') as f:
                f.write(self.files[path]);
    
    def write(self, path, data):
        if path not in self.files:
            self.files[path] = "";
        self.files[path] += data + "\n";


def ReplaceVariables(text, context, globalContext):
    for key in context:
        text = text.replace("<<" + key + ">>", str(context[key]))
        text = text.replace("<<_" + key + "_>>", str(context[key]).lower())
    for key in globalContext:
        text = text.replace("<<global." + key + ">>", str(globalContext[key]))
        text = text.replace("<<_global." + key + "_>>", str(globalContext[key]).lower())
    for key in context:
        text = text.replace("<<" + key + ">>", str(context[key]))
        text = text.replace("<<_" + key + "_>>", str(context[key]).lower())
    return text;

def IsAppliable(template, context):
    if "where" not in template:
        return True;

    conditions = template["where"];
    for key in conditions:
        if isinstance(conditions[key], list):
            if context[key] not in conditions[key]:
                return False;
        else:
            if key not in context:
                log.error("Key (" + key + ") not found in context: " + str(context));
                return False;
            if context[key] != conditions[key]:
                return False;
    return True;



def FilterContexts(template, contexts):
    instances = [];
    for i in contexts:
        if IsAppliable(template, i):
            instances.append(i);
        
    return instances;



def GroupBy(contexts, by):
    instances = {};
    
    for i in contexts:
        if i[by] not in instances:
            instances[i[by]] = [];
        instances[i[by]].append(i);
    
    groups = [];
    
    for group in instances:
        tmp = instances[group];
        groups.append({
            'group': group,
            'instances': json.dumps(tmp)
        });
    
    return groups;



def ProcessTemplate(basedir, template, context, globalContext, check = True):
    log.info("  Check if template is compatible with the next context"); 
    if check and not IsAppliable(template, context):
        return;
    
    path = template["target"];
    name = ReplaceVariables(template["name"], context, globalContext) + ".gen.yaml";
    log.info("  Continue processing template: " + name);

    try:
        log.info(template["template"]["lights"]["<<room>>"]["level_template"]);
    except:
        pass;
    walk_tree(template["template"]);
    writer.write(path + "/" + name, ReplaceVariables(yaml2.dump(template["template"]), context, globalContext))



# Main
writers = {};

for path in Path('/config/components').rglob('*.template.yaml'):
    log.info("Template found: " + str(path)); 
    
    basedir = str(path.parent);
    basepath = basedir;
    if basedir not in writers:
        writers[basedir] = BufferedWriter(basedir);
    
    writer = writers[basedir];
    
    with open(str(path)) as f:
        src = yaml2.load(f.read());

    log.info("YAML loaded: " + str(path)); 

    contexts = src["instances"];
    globalContext = src["global"];
    templates = src["templates"];
    summaries = src["summaries"];

    for template in templates:
        for context in contexts:
            ProcessTemplate(basedir, template, context, globalContext);
    
    for summary in summaries:
        instances = FilterContexts(summary, contexts);
        groups = GroupBy(instances, summary["group_by"]);
        for context in groups:
            for template in summary["each"]:
                ProcessTemplate(basedir, template, context, globalContext, False);

        if "final" in summary:
            finalContext = {
                'groups': json.dumps(groups),
                'entities': json.dumps(instances)
            };
            
            for template in summary["final"]:
                ProcessTemplate(basedir, template, finalContext, globalContext, False);

for writer in writers:
    writers[writer].flush();




















