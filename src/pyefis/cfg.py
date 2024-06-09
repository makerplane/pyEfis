import yaml
import os

# allows using include preferences and include: keys to include yaml files inside yaml files
# While it does support including includes within includes, it does not support the include: key being nested deeply.
#
# Rxamples:
# include: some_file.yaml <- supported
#
# test:
#  - include: some.yaml <- supported, when inside a list the included yaml needs to return a list inside items {items:[]}
#
# testing:
#  include: some.yaml <- supported, the keys inside some.yaml will be nested under testing
#
# testing:
#   deep:
#     include: some.yaml <- not supported
#
#
# Thi was made to split monolithic files into smaller includable sections
# Allowing users to easily swap sections in/out to configure the screens to their liking


def from_yaml(fname, bpath=None, cfg=None, bc=None, preferences=None):
    if bc == None:
        bc = list()
    bc.append(fname)
    if len(bc) > 500:
        import pprint

        raise RecursionError(
            f"{pprint.pformat(bc)}\nPotential loop detected inside yaml includes, the breadcrumbs above might help detect where the issue is"
        )

    fpath = os.path.dirname(fname)
    if not cfg and not fpath:
        raise SyntaxError(
            f"The filename '{fname}', must include the path, not just the filename"
        )
    if not cfg:
        # cfg only populated to process nested data
        if not bpath:
            bpath = fpath
        with open(fname) as cf:
            cfg = yaml.safe_load(cf)

    new = {}
    if hasattr(cfg, "items"):
        for key, val in cfg.items():
            if key == "include":
                if isinstance(val, str):
                    files = [val]
                elif isinstance(val, list):
                    files = val
                else:
                    raise SyntaxError(f"#include in {fname} must be string or array")
                # Process include(s)
                for f in files:
                    # Check if file relative to current file
                    ifile = fpath + "/" + f
                    if not os.path.exists(ifile):
                        # Use base path
                        ifile = bpath + "/" + f
                    if not os.path.exists(ifile):
                        # Check preferences
                        if preferences != None and "includes" in preferences:
                            pfile = preferences["includes"].get(f, False)
                            if pfile:
                                ifile = fpath + "/" + pfile
                                if not os.path.exists(ifile):
                                    ifile = bpath + "/" + pfile
                                    if not os.path.exists(ifile):
                                        raise FileNotFoundError(
                                            f"Cannot find include: {f}"
                                        )
                        else:
                            raise FileNotFoundError(f"Cannot find include: {f}")
                    sub = from_yaml(ifile, bpath, bc=bc, preferences=preferences)
                    if hasattr(sub, "items"):
                        for k, v in sub.items():
                            new[k] = v
                    else:
                        # Not sure if this is correct error text, also not sure how to get here because I think one can only return a dict from base yaml
                        # Even bad syntax never gets here
                        raise SyntaxError(
                            f"Error in {fname}\nWhen including list items they need listed under 'items:' in the include file"
                        )
            elif isinstance(val, dict):
                new[key] = from_yaml(fname, bpath, val, bc=bc, preferences=preferences)
            elif isinstance(val, list):
                new[key] = []
                # Included array elements
                for l in val:
                    if isinstance(l, dict):
                        if "include" in l:
                            ifile = fpath + "/" + l["include"]
                            if not os.path.exists(ifile):
                                # Use base path
                                ifile = bpath + "/" + l["include"]
                            if not os.path.exists(ifile):
                                # Check preferences
                                if "includes" in preferences:
                                    pfile = preferences["includes"].get(
                                        l["include"], False
                                    )
                                    if pfile:
                                        ifile = fpath + "/" + pfile
                                        if not os.path.exists(ifile):
                                            ifile = bpath + "/" + pfile
                                            if not os.path.exists(ifile):
                                                raise FileNotFoundError(
                                                    f"Cannot find include: {f}"
                                                )
                                else:
                                    raise FileNotFoundError(f"Cannot find include: {f}")
                            # with open(ifile) as cf:
                            litems = from_yaml(
                                ifile, bpath, bc=bc, preferences=preferences
                            )  # yaml.safe_load(cf)
                            if "items" in litems:
                                if litems["items"] != None:
                                    for a in litems["items"]:
                                        # What about nested things?
                                        ap = a
                                        if isinstance(a, dict):
                                            ap = from_yaml(
                                                ifile,
                                                bpath,
                                                a,
                                                bc=bc,
                                                preferences=preferences,
                                            )
                                        if isinstance(litems["items"], dict):
                                            new[key].append({ap: litems["items"][ap]})
                                        else:
                                            new[key].append(ap)
                            else:
                                raise SyntaxError(
                                    f"Error in {ifile}\nWhen including list items they need listed under 'items:' in the include file"
                                )
                        else:
                            new[key].append(l)
                    else:
                        new[key].append(l)
            else:
                # Save existing
                new[key] = val
    return new
