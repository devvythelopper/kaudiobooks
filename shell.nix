{ pkgs ? import <nixpkgs> {} }: 
pkgs.mkShell {
  buildInputs = with pkgs; [ 
    poetry
    python3
  ] ++ (with python3Packages; [
    virtualenv
    pip
  ]);
}
