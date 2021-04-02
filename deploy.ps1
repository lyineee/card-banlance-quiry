$remotePath = "~/dev/card-bill/";
$composeFilePath = "~/dev/"
$fileList = "main.py", # main
            "student_card.py",
            "free_class.py",
            "requirements.txt", # pip
            "dockerfile" # docker
foreach ($item in $fileList) {
    scp -r $item server2:$remotePath;
}
# ssh server ("cd {0};docker-compose down --rmi local;docker-compose up -d" -f $remotePath)
ssh server2 ("cd {0}; docker-compose up --build -d card-bill" -f $composeFilePath)