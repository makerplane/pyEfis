import yaml
import os

def from_yaml(fname,bpath=None,cfg=None,bc=[],preferences=None):
    bc.append(fname)
    if len(bc) > 500:
        import pprint
        raise Exception(f"{pprint.pformat(bc)}\nPotential loop detected inside yaml includes, the breadcrumbs above might help detect where the issue is")
        
    fpath = os.path.dirname(fname)
    if not cfg:
        # cfg only populated to process nested data
        if not bpath: bpath = fpath
        cfg = yaml.safe_load(open(fname))
    new = {}
    if hasattr(cfg,'items'):
        for key, val in cfg.items():
            if key == 'include':
                if isinstance(val, str):
                    files = [ val ]
                elif isinstance(val, list):
                    files = val
                else:
                    raise Exception(f"#include in {fname} must be string or array")
                # Process include(s)
                for f in files:
                    # Check if file relative to current file
                    ifile = fpath + '/' + f
                    if not os.path.exists(ifile):
                        # Use base path
                        ifile = bpath + '/' + f
                    if not os.path.exists(ifile):
                        # Check preferences
                        if 'includes' in preferences:
                            pfile = preferences['includes'].get(f,False)
                            if pfile:
                                ifile = fpath + '/' + pfile
                                if not os.path.exists(ifile):
                                    ifile = bpath + '/' + pfile
                                    if not os.path.exists(ifile):
                                        raise Exception(f"Cannot find include: {f}")
                        else:
                            raise Exception(f"Cannot find include: {f}")
                    sub = from_yaml(ifile, bpath,bc=bc,preferences=preferences)
                    if hasattr(sub,'items'):
                       for k, v in sub.items():
                           new[k] = v
                    else:
                        raise Exception(f"Include {val} from {fname} is invalid")                    
            elif isinstance(val, dict):
                new[key] = from_yaml(fname,bpath,val,bc=bc,preferences=preferences)
            elif isinstance(val, list):
                new[key] = []
                # Included array elements
                for l in val:
                    if isinstance(l, dict):
                        if 'include' in l:
                            ifile = fpath + '/' + l['include']
                            if not os.path.exists(ifile):
                                # Use base path
                                ifile = bpath + '/' + l['include']
                            if not os.path.exists(ifile):
                                # Check preferences
                                if 'includes' in preferences:
                                    pfile = preferences['includes'].get(l['include'],False)
                                    if pfile:
                                        ifile = fpath + '/' + pfile
                                        if not os.path.exists(ifile):
                                            ifile = bpath + '/' + pfile
                                            if not os.path.exists(ifile):
                                                raise Exception(f"Cannot find include: {f}")
                                else:
                                    raise Exception(f"Cannot find include: {f}")
                            litems = yaml.safe_load(open(ifile))
                            if 'items' in litems:
                                if litems['items'] != None:
                                    for a in litems['items']:
                                        new[key].append(a)
                            else:
                                raise Exception(f"Error in {ifile}\nWhen including list items they need listed under 'items:' in the include file")
                        else:
                            new[key].append(l)
                    else:
                        new[key].append(l)
            else:
                #Save existing
                new[key] = val
    return new

