# Copyright (C) 2008-2011 Dejan Muhamedagic <dmuhamedagic@suse.de>
# Copyright (C) 2013 Kristoffer Gronlund <kgronlund@suse.com>
# See COPYING for license information.

from . import command
from . import completers as compl
from . import utils
from . import ra
from . import constants
from . import options
from . import config
from . import msg as msglog


def complete_class_provider_type(args):
    '''
    This is just too complicated to complete properly...
    '''
    ret = set([])
    classes = ra.ra_classes()
    for c in classes:
        if c != 'ocf':
            types = ra.ra_types(c)
            for t in types:
                ret.add('%s:%s' % (c, t))

    providers = ra.ra_providers_all('ocf')
    for p in providers:
        types = ra.ra_types('ocf', p)
        for t in types:
            ret.add('ocf:%s:%s' % (p, t))
    return list(ret)


class RA(command.UI):
    '''
    CIB shadow management class
    '''
    name = "ra"
    provider_classes = ["ocf"]

    def do_classes(self, context):
        "usage: classes"
        for c in ra.ra_classes():
            if c in self.provider_classes:
                providers = ra.ra_providers_all(c)
                if providers:
                    print "%s / %s" % (c, ' '.join(providers))
            else:
                print "%s" % c

    @command.skill_level('administrator')
    def do_providers(self, context, ra_type, ra_class="ocf"):
        "usage: providers <ra> [<class>]"
        print ' '.join(ra.ra_providers(ra_type, ra_class))

    @command.skill_level('administrator')
    @command.completers(compl.call(ra.ra_classes), lambda args: ra.ra_providers_all(args[1]))
    def do_list(self, context, class_, provider_=None):
        "usage: list <class> [<provider>]"
        if class_ not in ra.ra_classes():
            context.fatal_error("class %s does not exist" % class_)
        if provider_ and provider_ not in ra.ra_providers_all(class_):
            context.fatal_error("there is no provider %s for class %s" % (provider_, class_))
        types = ra.ra_types(class_, provider_)
        if options.regression_tests:
            for t in types:
                print t
        else:
            utils.multicolumn(types)

    @command.skill_level('administrator')
    @command.alias('meta')
    @command.completers(complete_class_provider_type)
    def do_info(self, context, *args):
        "usage: info [<class>:[<provider>:]]<type>"
        if len(args) == 0:
            context.fatal_error("Expected [<class>:[<provider>:]]<type>")
        elif len(args) > 1:  # obsolete syntax
            if len(args) < 3:
                ra_type, ra_class, ra_provider = args[0], args[1], "heartbeat"
            else:
                ra_type, ra_class, ra_provider = args[0], args[1], args[2]
        elif args[0] in constants.meta_progs:
            ra_class, ra_provider, ra_type = args[0], None, None
        else:
            ra_class, ra_provider, ra_type = ra.disambiguate_ra_type(args[0])
        agent = ra.RAInfo(ra_class, ra_type, ra_provider)
        if agent.mk_ra_node() is None:
            return False
        try:
            utils.page_string(agent.meta_pretty())
        except Exception, msg:
            context.fatal_error(msg)

    @command.skill_level('administrator')
    def do_validate(self, context, agentname, *params):
        "usage: validate [<class>:[<provider>:]]<type> [<key>=<value> ...]"
        c, p, t = ra.disambiguate_ra_type(agentname)
        if c != "ocf":
            context.error("Only OCF agents are supported by this command")
        agent = ra.RAInfo(c, t, p)
        if agent.mk_ra_node() is None:
            return False
        if len(agent.ra_elem.xpath('//actions/action[@name="validate-all"]')) < 1:
            context.error("validate-all action not supported by agent")

        import subprocess
        import os
        my_env = os.environ.copy()
        my_env["OCF_ROOT"] = config.path.ocf_root
        for param in params:
            k, v = param.split('=', 1)
            my_env["OCF_RESKEY_" + k] = v
        p = subprocess.Popen([os.path.join(config.path.ocf_root, "resource.d", p, t), "validate-all"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=my_env)
        out, _ = p.communicate()
        for msg in out.splitlines():
            if msg.startswith("ERROR: "):
                msglog.err_buf.error(msg[7:])
            elif msg.startswith("WARNING: "):
                msglog.err_buf.warning(msg[9:])
            elif msg.startswith("INFO: "):
                msglog.err_buf.info(msg[6:])
            elif msg.startswith("DEBUG: "):
                msglog.err_buf.debug(msg[7:])
            else:
                msglog.err_buf.writemsg(msg)
        p.wait()
        return p.returncode == 0
