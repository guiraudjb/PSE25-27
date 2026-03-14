#!/bin/bash
git status 
if [[ $(git status | grep "rien à valider" | wc -l) -eq 1 ]]
then
exit 0
fi
echo " motif de mise à jour ?"
read motif
git add --all
git commit -m"$motif"
git push -u origin main
exit 0
