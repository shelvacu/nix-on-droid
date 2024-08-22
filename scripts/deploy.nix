# Copyright (c) 2019-2022, see AUTHORS. Licensed under MIT License, see LICENSE.

{ nixpkgs, system }:

let
  pkgs = nixpkgs.legacyPackages.${system};
  pypkgs = pkgs.python3Packages;
  scriptText = builtins.readFile ./deploy.py;
  modifiedScriptText = builtins.replaceStrings
    [ "@nix@" "@git@" "@rsync@" ]
    (map builtins.toString [ pkgs.nix pkgs.git pkgs.rsync ])
    scriptText;
  libraries = [ pkgs.python3Packages.click ];
  flakeIgnore = [
    "E501" # line too long
    "E402" # module level import not at top of file: we purposefully don't import click and such so that users that try to run the script directly get a friendly error
  ];
  disablePyLints = [
    "line-too-long"
    "missing-module-docstring"
    "wrong-import-position" # import should be at top of file: we purposefully don't import click and such so that users that try to run the script directly get a friendly error
    "missing-function-docstring"
    # c'mon, it's a script
    "too-many-locals"
    "too-many-branches"
    "too-many-statements"
  ];
  script = pkgs.writers.writePython3 "deploy" { inherit libraries flakeIgnore; } modifiedScriptText;
  deriv = pkgs.stdenv.mkDerivation {
    pname = "deploy";
    version = "0.0";
    src = ./deploy.py;

    inherit (pkgs) nix git rsync;

    doCheck = true;
    nativeCheckInputs = with pypkgs; [ mypy pylint black ];
    checkPhase = ''
      mypy --strict --no-color script.py
      pylint --disable=${pkgs.lib.concatStringsSep "," disablePyLints} script.py
      black --check --diff script.py
    '';

    unpackPhase = "cp $src script.py";
    patchPhase = ''
      substituteInPlace script.py \
        --subst-var nix \
        --subst-var git \
        --subst-var rsync
    '';
    installPhase = "cp script.py $out";
  };
in
deriv
#script
