import yaml
import os

def from_yaml(fname,bpath=None,cfg=None,bc=[]):
    bc.append(fname)
    if len(bc) > 500:
        import pprint
        raise Exception(f"{pprint.pformat(bc)}\nPotential loop detected inside yaml includes, the breadcrumbs above might help detect where the issue is")
        
    fpath = os.path.dirname(fname)
    if not cfg:
        # cfg only populated to process nested data
        cf = open(fname)
        if not bpath: bpath = fpath
        cfg = yaml.safe_load(cf)
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
                    sub = from_yaml(ifile, bpath,bc=bc)
                    if hasattr(sub,'items'):
                       for k, v in sub.items():
                           new[k] = v
                    else:
                        raise Exception(f"Include {val} from {fname} is invalid")                    
            elif isinstance(val, dict):
                new[key] = from_yaml(fname,bpath,val,bc=bc)
            else:
                #Save existing
                new[key] = val
    return new

